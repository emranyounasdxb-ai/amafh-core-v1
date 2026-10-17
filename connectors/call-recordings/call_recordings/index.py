"""SQLite metadata index and change journal.

The database lives outside the recording archive. Rollback journal mode is
required: this process's SQLite must not enable WAL. Streams take a short
lookup and then release the connection before any audio read.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid5

from .contract import CONTRACT_VERSION

_NAMESPACE = UUID("6f1d7a2e-4c3b-5d8e-9a10-b2c3d4e5f607")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class CatalogIndex:
    def __init__(self, path: Path, *, journal_keep: int = 50_000):
        self.path = path
        self.journal_keep = journal_keep
        self._lock = threading.Lock()
        self._connection: sqlite3.Connection | None = None

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        connection.row_factory = sqlite3.Row
        mode = connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
        if str(mode).lower() == "wal":
            connection.close()
            raise RuntimeError("SQLite WAL is disabled for this connector runtime")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
        self._migrate(connection)
        self._connection = connection
        with self._lock:
            # Version 1 accepted only ten-digit destination numbers and could
            # checkpoint past unsettled files. Revisit metadata in place once;
            # keep IDs, the epoch, journal and existing playable catalog intact.
            if self._value("number_format_revision") != "2":
                self._execute("BEGIN IMMEDIATE")
                try:
                    self._execute("DELETE FROM meta WHERE key IN ('reconcile_checkpoint', 'last_indexed_at')")
                    self._upsert_meta("phase", "indexing")
                    self._upsert_meta("number_format_revision", "2")
                    self._execute("COMMIT")
                except Exception:
                    self._execute("ROLLBACK")
                    raise
            self._execute(
                "INSERT INTO meta(key, value) VALUES('contract', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(CONTRACT_VERSION),),
            )
            if self._value("epoch") is None:
                from uuid import uuid4

                self._execute(
                    "INSERT INTO meta(key, value) VALUES('epoch', ?)",
                    (str(uuid4()),),
                )

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def _migrate(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recordings (
                id TEXT PRIMARY KEY,
                relative_path TEXT NOT NULL UNIQUE,
                month TEXT,
                customer_number TEXT,
                extension TEXT,
                filename TEXT NOT NULL,
                byte_size INTEGER,
                file_version TEXT,
                availability TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                indexed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS journal (
                sequence INTEGER PRIMARY KEY,
                recording_id TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_recordings_month
                ON recordings(month, customer_number, filename);
            """
        )
        names = {row["name"] for row in connection.execute("PRAGMA table_info(recordings)")}
        if "fingerprint" not in names:
            connection.execute("ALTER TABLE recordings ADD COLUMN fingerprint TEXT")

    def _execute(self, sql: str, params: tuple = ()):
        if self._connection is None:
            raise RuntimeError("Index is closed")
        return self._connection.execute(sql, params)

    def _value(self, key: str) -> str | None:
        row = self._execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else row["value"]

    def epoch(self) -> str:
        with self._lock:
            value = self._value("epoch")
        if value is None:
            raise RuntimeError("Index has no epoch")
        return value

    def status(self) -> dict:
        with self._lock:
            minimum = self._execute("SELECT MIN(sequence) AS value FROM journal").fetchone()["value"]
            maximum = self._execute("SELECT MAX(sequence) AS value FROM journal").fetchone()["value"]
            count = self._execute(
                "SELECT COUNT(*) AS value FROM recordings WHERE availability != 'pending'"
            ).fetchone()["value"]
            return {
                "contractVersion": CONTRACT_VERSION,
                "epoch": self._value("epoch"),
                "processReady": True,
                "indexReady": self._value("last_indexed_at") is not None,
                "phase": self._value("phase") or "indexing",
                "lastIndexedAt": self._value("last_indexed_at"),
                "journalMin": int(minimum or 0),
                "journalMax": int(maximum or 0),
                "recordingCount": int(count or 0),
            }

    def set_phase(self, phase: str, *, indexed: bool = False) -> None:
        with self._lock:
            self._upsert_meta("phase", phase)
            if indexed:
                self._upsert_meta("last_indexed_at", _now())

    def _upsert_meta(self, key: str, value: str) -> None:
        self._execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def recording_id(self, relative_path: str) -> str:
        return str(uuid5(_NAMESPACE, relative_path))

    def checkpoint(self) -> tuple[str, str]:
        with self._lock:
            raw = self._value("reconcile_checkpoint") or ""
        month, separator, name = raw.partition("\n")
        if not separator:
            return "", ""
        return month, name

    def set_checkpoint(self, month: str, filename: str) -> None:
        with self._lock:
            if not month and not filename:
                self._execute("DELETE FROM meta WHERE key = 'reconcile_checkpoint'")
                return
            self._upsert_meta("reconcile_checkpoint", f"{month}\n{filename}")

    def has_checkpoint(self) -> bool:
        month, _filename = self.checkpoint()
        return bool(month)

    def upsert(self, relative_path: str, filename: str, fields: dict) -> None:
        with self._lock:
            self._execute("BEGIN IMMEDIATE")
            try:
                current = self._execute(
                    "SELECT * FROM recordings WHERE relative_path = ?",
                    (relative_path,),
                ).fetchone()
                sequence = int(self._value("sequence") or "0") + 1
                recording_id = current["id"] if current else self.recording_id(relative_path)
                payload = {
                    "id": recording_id,
                    "availability": fields["availability"],
                    "month": fields.get("month"),
                    "customerNumber": fields.get("customer_number"),
                    "extension": fields.get("extension"),
                    "filename": filename,
                    "byteSize": fields.get("byte_size"),
                    "fileVersion": fields.get("file_version"),
                    "indexedAt": _now(),
                    "sequence": sequence,
                }
                changed = current is None or any(
                    current[column] != fields.get(column)
                    for column in (
                        "availability",
                        "byte_size",
                        "file_version",
                        "customer_number",
                        "extension",
                        "month",
                    )
                )
                if changed:
                    self._execute(
                        """
                        INSERT INTO recordings(
                            id, relative_path, month, customer_number, extension, filename,
                            byte_size, file_version, availability, sequence, indexed_at,
                            fingerprint
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(relative_path) DO UPDATE SET
                            month=excluded.month,
                            customer_number=excluded.customer_number,
                            extension=excluded.extension,
                            filename=excluded.filename,
                            byte_size=excluded.byte_size,
                            file_version=excluded.file_version,
                            availability=excluded.availability,
                            sequence=excluded.sequence,
                            indexed_at=excluded.indexed_at,
                            fingerprint=excluded.fingerprint
                        """,
                        (
                            recording_id,
                            relative_path,
                            fields.get("month"),
                            fields.get("customer_number"),
                            fields.get("extension"),
                            filename,
                            fields.get("byte_size"),
                            fields.get("file_version"),
                            fields["availability"],
                            sequence,
                            payload["indexedAt"],
                            fields.get("fingerprint"),
                        ),
                    )
                    self._execute(
                        "INSERT INTO journal(sequence, recording_id, payload) VALUES(?, ?, ?)",
                        (sequence, recording_id, json.dumps(payload, separators=(",", ":"))),
                    )
                    self._upsert_meta("sequence", str(sequence))
                    self._compact(sequence)
                self._execute("COMMIT")
            except Exception:
                self._execute("ROLLBACK")
                raise

    def mark_missing(self, month: str, present: set[str]) -> None:
        with self._lock:
            rows = self._execute(
                """
                SELECT relative_path, filename, customer_number, extension, byte_size, file_version
                FROM recordings
                WHERE month = ? AND availability != 'missing'
                """,
                (month,),
            ).fetchall()
        for row in rows:
            filename = row["filename"]
            if filename not in present:
                self.upsert(
                    row["relative_path"],
                    filename,
                    {
                        "availability": "missing",
                        "month": month,
                        "customer_number": row["customer_number"],
                        "extension": row["extension"],
                        "byte_size": row["byte_size"],
                        "file_version": row["file_version"],
                    },
                )

    def _compact(self, latest: int) -> None:
        floor = latest - self.journal_keep
        if floor > 0:
            self._execute("DELETE FROM journal WHERE sequence <= ?", (floor,))

    def changes(self, after: int, limit: int) -> dict | None:
        with self._lock:
            minimum = self._execute("SELECT MIN(sequence) AS value FROM journal").fetchone()["value"]
            if minimum is not None and after + 1 < int(minimum):
                return None
            rows = self._execute(
                "SELECT payload FROM journal WHERE sequence > ? ORDER BY sequence LIMIT ?",
                (after, limit),
            ).fetchall()
            maximum = self._execute("SELECT MAX(sequence) AS value FROM journal").fetchone()["value"]
        items = [json.loads(row["payload"]) for row in rows]
        through = items[-1]["sequence"] if items else after
        return {
            "contractVersion": CONTRACT_VERSION,
            "epoch": self.epoch(),
            "after": after,
            "through": through,
            "journalMax": int(maximum or 0),
            "changes": items,
        }

    def snapshot(self, cursor: str, limit: int) -> dict:
        with self._lock:
            rows = self._execute(
                """
                SELECT id, availability, month, customer_number, extension, filename,
                       byte_size, file_version, indexed_at, sequence
                FROM recordings
                WHERE availability != 'pending' AND id > ?
                ORDER BY id
                LIMIT ?
                """,
                (cursor, limit),
            ).fetchall()
            epoch = self._value("epoch")
        items = [
            {
                "id": row["id"],
                "availability": row["availability"],
                "month": row["month"],
                "customerNumber": row["customer_number"],
                "extension": row["extension"],
                "filename": row["filename"],
                "byteSize": row["byte_size"],
                "fileVersion": row["file_version"],
                "indexedAt": row["indexed_at"],
                "sequence": row["sequence"],
            }
            for row in rows
        ]
        next_cursor = items[-1]["id"] if items else cursor
        return {
            "contractVersion": CONTRACT_VERSION,
            "epoch": epoch,
            "cursor": cursor,
            "nextCursor": next_cursor,
            "complete": len(items) < limit,
            "recordings": items,
        }

    def get(self, recording_id: str) -> dict | None:
        with self._lock:
            row = self._execute("SELECT * FROM recordings WHERE id = ?", (recording_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def sqlite_version(self) -> str:
        with self._lock:
            return self._execute("SELECT sqlite_version()").fetchone()[0]
