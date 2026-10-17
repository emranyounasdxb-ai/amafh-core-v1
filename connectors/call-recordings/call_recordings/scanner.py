"""Incremental index of immediate YYYY-MM folders.

A failed or incomplete listing never marks the rest of the archive missing.
Unchanged ready files are recognized from a persisted size and mtime fingerprint
and are not opened again. A pass stops after a bounded number of opens and
resumes from a checkpoint. Events from the watcher are hints; reconciliation
is the authority. Audio is not hashed.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import struct
import threading
from pathlib import Path

from .index import CatalogIndex
from .parser import parse_filename, parse_month
from .safety import (
    SourcePending,
    SourceUnsafe,
    directory_is_reparse,
    file_identity,
    open_checked,
    wav_payload_complete,
)

OPEN_BUDGET = 200
LOGGER = logging.getLogger(__name__)


class Scanner:
    def __init__(
        self,
        index: CatalogIndex,
        root: Path,
        root_final: str,
        *,
        settle_seconds: float,
        reconcile_seconds: float,
    ):
        self.index = index
        self.root = root
        self.root_final = root_final
        self.settle_seconds = settle_seconds
        self.reconcile_seconds = reconcile_seconds
        self.open_budget = OPEN_BUDGET
        self._stop = threading.Event()
        self._dirty = threading.Event()
        self._priority: set[str] = set()
        self._thread: threading.Thread | None = None
        self._seen: dict[str, tuple[int, int]] = {}
        self._seen_at: dict[str, float] = {}
        self._clock = __import__("time").monotonic

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        self.index.set_phase("indexing")
        self._thread = threading.Thread(target=self._loop, name="call-recording-index", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 20) -> None:
        self._stop.set()
        self._dirty.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def hint(self, months=None) -> None:
        if months:
            for month in months:
                parsed = parse_month(str(month))
                if parsed is not None:
                    self._priority.add(parsed)
        self._dirty.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.reconcile()
            if self._stop.is_set():
                return
            if self.index.has_checkpoint():
                if self._stop.wait(0.05):
                    return
                continue
            self._dirty.wait(self.reconcile_seconds)
            self._dirty.clear()

    def reconcile(self) -> None:
        if self._stop.is_set():
            return
        if not self.root.exists() or directory_is_reparse(self.root):
            self.index.set_phase("offline")
            return
        try:
            months = self._months()
        except OSError:
            self.index.set_phase("offline")
            return
        cursor_month, cursor_file = self.index.checkpoint()
        if cursor_month and cursor_month not in months:
            cursor_month, cursor_file = "", ""
            self.index.set_checkpoint("", "")
        priority = [month for month in sorted(self._priority) if month in months]
        self._priority.clear()
        opens = 0
        budget = max(1, int(self.open_budget))
        for month in priority:
            if self._stop.is_set() or opens >= budget:
                self.index.set_phase("indexing")
                return
            outcome, opens = self._scan_month(
                month, opens, budget, skip_through="", persist=False
            )
            if outcome != "done":
                self.index.set_phase("indexing")
                return
        for index, month in enumerate(months):
            if month in priority:
                continue
            if self._stop.is_set():
                return
            if cursor_month and month < cursor_month:
                continue
            if opens >= budget:
                self.index.set_checkpoint(month, "")
                self.index.set_phase("indexing")
                return
            skip = cursor_file if month == cursor_month else ""
            outcome, opens = self._scan_month(
                month, opens, budget, skip_through=skip, persist=True
            )
            if outcome == "error":
                self.index.set_phase("indexing")
                return
            if outcome == "stop":
                self.index.set_phase("indexing")
                return
            following = next((later for later in months[index + 1 :] if later not in priority), "")
            self.index.set_checkpoint(following, "")
            cursor_month, cursor_file = following, ""
        if self._stop.is_set():
            return
        self.index.set_checkpoint("", "")
        self.index.set_phase("ready", indexed=True)

    def _scan_month(
        self,
        month: str,
        opens: int,
        budget: int,
        *,
        skip_through: str,
        persist: bool,
    ) -> tuple[str, int]:
        try:
            names = self._files(month)
        except OSError:
            return "error", opens
        if names is None:
            return "done", opens
        names = sorted(names)

        def remember(filename: str) -> None:
            if persist:
                self.index.set_checkpoint(month, filename)

        for name in names:
            if self._stop.is_set():
                return "stop", opens
            if skip_through and name <= skip_through:
                continue
            if opens >= budget:
                remember(skip_through)
                return "stop", opens
            failed = False
            try:
                opened = self._observe(month, name)
            except AssertionError:
                raise
            except (OSError, sqlite3.Error, struct.error, UnicodeError, ValueError):
                LOGGER.exception("Skipped call recording %s/%s", month, name)
                failed = True
            if failed:
                continue
            if opened:
                opens += 1
            skip_through = name
            remember(name)
        self.index.mark_missing(month, set(names))
        if opens >= budget:
            return "stop", opens
        return "done", opens

    def _months(self) -> list[str]:
        found = []
        with os.scandir(self.root) as entries:
            for entry in entries:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                month = parse_month(entry.name)
                if month is None:
                    continue
                if directory_is_reparse(Path(entry.path)):
                    continue
                found.append(month)
        return sorted(found)

    def _files(self, month: str) -> list[str] | None:
        folder = self.root / month
        if directory_is_reparse(folder):
            return None
        names = []
        with os.scandir(folder) as entries:
            for entry in entries:
                if not entry.is_file(follow_symlinks=False):
                    continue
                names.append(entry.name)
        return names

    def _observe(self, month: str, filename: str) -> bool:
        relative = f"{month}/{filename}"
        parsed = parse_filename(filename)
        if parsed is None or not parsed.supported:
            self.index.upsert(
                relative,
                filename,
                {
                    "availability": "unsupported",
                    "month": month,
                    "customer_number": None if parsed is None else parsed.customer_number,
                    "extension": None if parsed is None else parsed.extension_number,
                    "byte_size": None,
                    "file_version": None,
                },
            )
            return False
        path = self.root / month / filename
        try:
            first = path.stat()
        except OSError:
            self._remember_pending(relative, month, filename, parsed)
            return False
        identity = file_identity(path)
        fingerprint = f"{first.st_size}:{first.st_mtime_ns}:{identity or ''}"
        current = self.index.get(self.index.recording_id(relative))
        if (
            identity
            and current is not None
            and current["availability"] == "ready"
            and current.get("fingerprint") == fingerprint
            and current.get("byte_size") == first.st_size
        ):
            return False
        try:
            with open_checked(self.root_final, path) as opened:
                complete = wav_payload_complete(opened)
                version = opened.version
                size = opened.size
            second = path.stat()
        except SourcePending:
            self._remember_pending(relative, month, filename, parsed)
            return True
        except SourceUnsafe:
            return True
        except OSError:
            self._remember_pending(relative, month, filename, parsed)
            return True
        if first.st_size != second.st_size or first.st_mtime_ns != second.st_mtime_ns:
            self._remember_pending(relative, month, filename, parsed)
            return True
        key = (size, first.st_mtime_ns)
        now = self._clock()
        previous = self._seen.get(relative)
        if previous != key:
            self._seen[relative] = key
            self._seen_at[relative] = now
            if self.settle_seconds > 0:
                self._remember_pending(relative, month, filename, parsed, size, version)
                return True
        settled = now - self._seen_at.get(relative, now)
        if self.settle_seconds > 0 and settled < self.settle_seconds:
            self._remember_pending(relative, month, filename, parsed, size, version)
            return True
        if size <= 0 or not complete:
            self._remember_pending(relative, month, filename, parsed, size, version)
            return True
        self.index.upsert(
            relative,
            filename,
            {
                "availability": "ready",
                "month": month,
                "customer_number": parsed.customer_number,
                "extension": parsed.extension_number,
                "byte_size": size,
                "file_version": version,
                "fingerprint": fingerprint,
            },
        )
        return True

    def _remember_pending(self, relative, month, filename, parsed, size=None, version=None) -> None:
        self.index.upsert(
            relative,
            filename,
            {
                "availability": "pending",
                "month": month,
                "customer_number": parsed.customer_number,
                "extension": parsed.extension_number,
                "byte_size": size,
                "file_version": version,
            },
        )
