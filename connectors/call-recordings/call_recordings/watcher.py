"""Filesystem hints for the recording root.

Directory modification times are checked twice a second. A change only wakes
reconciliation. Missed or duplicate notices are harmless because the scanner
still reconciles on its interval. The wait is interruptible so shutdown does
not leave the directory handle or the thread behind.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path


class Watcher:
    def __init__(self, root: Path, on_hint):
        self.root = root
        self.on_hint = on_hint
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="call-recording-watch", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        previous = self._stamp()
        while not self._stop.wait(0.5):
            current = self._stamp()
            if current != previous:
                self.on_hint(_changed_months(previous, current))
                previous = current

    def _stamp(self) -> tuple:
        try:
            stamps = [self.root.stat().st_mtime_ns]
            with os.scandir(self.root) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        stamps.append((entry.name, entry.stat(follow_symlinks=False).st_mtime_ns))
            return tuple(stamps)
        except OSError:
            return ()


def _changed_months(previous: tuple, current: tuple) -> list[str]:
    old = {name: stamp for name, stamp in previous[1:]} if len(previous) > 1 else {}
    new = {name: stamp for name, stamp in current[1:]} if len(current) > 1 else {}
    changed = [name for name, stamp in new.items() if old.get(name) != stamp]
    changed.extend(name for name in old if name not in new)
    return changed
