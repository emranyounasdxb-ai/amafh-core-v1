"""PostgreSQL 18 snapshot export and empty-target restore."""

import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

from app.backup.config import BackupError

_QUERY_ENV = {
    "sslmode": "PGSSLMODE",
    "sslrootcert": "PGSSLROOTCERT",
    "sslcert": "PGSSLCERT",
    "sslkey": "PGSSLKEY",
    "options": "PGOPTIONS",
    "connect_timeout": "PGCONNECT_TIMEOUT",
}


@dataclass(frozen=True)
class DatabaseSpec:
    host: str
    port: int
    name: str
    user: str
    password: str
    options: dict[str, str]

    @classmethod
    def from_url(cls, raw: str) -> DatabaseSpec:
        try:
            url = make_url(raw)
            if url.drivername != "postgresql+psycopg":
                raise ValueError
            if not all((url.host, url.database, url.username)):
                raise ValueError
            options = {}
            for key, value in url.query.items():
                if key not in _QUERY_ENV or not isinstance(value, str):
                    raise ValueError
                options[key] = value
            return cls(
                host=url.host or "",
                port=url.port or 5432,
                name=url.database or "",
                user=url.username or "",
                password=url.password or "",
                options=options,
            )
        except (TypeError, ValueError) as exc:
            raise BackupError("Unsupported PostgreSQL connection configuration") from exc

    def connect(self) -> psycopg.Connection:
        try:
            return psycopg.connect(
                host=self.host,
                port=self.port,
                dbname=self.name,
                user=self.user,
                password=self.password,
                autocommit=True,
                **self.options,  # type: ignore[arg-type]
            )
        except psycopg.Error as exc:
            raise BackupError("PostgreSQL connection failed") from exc

    def process_environment(self) -> dict[str, str]:
        env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
        env.update(
            PGHOST=self.host,
            PGPORT=str(self.port),
            PGDATABASE=self.name,
            PGUSER=self.user,
            PGPASSWORD=self.password,
        )
        for option, name in _QUERY_ENV.items():
            if option in self.options:
                env[name] = self.options[option]
        return env


def _run(arguments: list[str], *, env: dict[str, str] | None = None) -> None:
    try:
        result = subprocess.run(
            arguments,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
            timeout=60 * 60 * 4,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackupError("PostgreSQL utility failed") from exc
    if result.returncode != 0:
        raise BackupError("PostgreSQL utility failed")


def require_pg18_tool(executable: Path, expected_name: str) -> None:
    if executable.name.lower() not in {expected_name, f"{expected_name}.exe"}:
        raise BackupError("Configured PostgreSQL utility name is invalid")
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackupError("PostgreSQL 18 utility is unavailable") from exc
    if result.returncode or not re.search(r"PostgreSQL\)? 18(?:\.|\s|$)", result.stdout):
        raise BackupError("PostgreSQL 18 utility is required")


def _require_pg18_server(conn: psycopg.Connection) -> None:
    row = conn.execute("SHOW server_version_num").fetchone()
    if row is None:
        raise BackupError("PostgreSQL version check failed")
    version = int(row[0])
    if not 180000 <= version < 190000:
        raise BackupError("PostgreSQL 18 server is required")


@contextmanager
def source_snapshot(spec: DatabaseSpec) -> Iterator[tuple[str, list[tuple[str, str, int]]]]:
    try:
        with spec.connect() as conn:
            _require_pg18_server(conn)
            conn.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            try:
                row = conn.execute("SELECT pg_export_snapshot()").fetchone()
                if row is None:
                    raise BackupError("PostgreSQL snapshot export failed")
                snapshot = str(row[0])
                records = conn.execute(
                    "SELECT kind, storage_key, byte_size FROM stored_files ORDER BY storage_key"
                ).fetchall()
                yield snapshot, [(str(kind), str(key), int(size)) for kind, key, size in records]
            finally:
                conn.execute("ROLLBACK")
    except psycopg.Error as exc:
        raise BackupError("PostgreSQL snapshot export failed") from exc


def dump_snapshot(spec: DatabaseSpec, executable: Path, snapshot: str, output: Path) -> None:
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    _run(
        [
            str(executable),
            "--format=custom",
            "--no-owner",
            "--no-acl",
            f"--snapshot={snapshot}",
            f"--file={output}",
        ],
        env=spec.process_environment(),
    )
    if output.stat().st_size == 0:
        raise BackupError("PostgreSQL dump is empty")


def inspect_dump(executable: Path, dump_path: Path) -> None:
    _run([str(executable), "--list", str(dump_path)])
    # Render the entire custom archive to the OS null device. Unlike --list,
    # this reads and decompresses table contents without changing a database.
    _run(
        [
            str(executable),
            "--no-owner",
            "--no-acl",
            f"--file={os.devnull}",
            str(dump_path),
        ]
    )


def restore_to_empty_target(
    source_database_name: str, target: DatabaseSpec, executable: Path, dump_path: Path
) -> None:
    # A distinct empty database is the only supported destination. Cutover is a
    # separate operator procedure; this command never replaces a live database.
    if target.name == source_database_name:
        raise BackupError("Restore target database name must differ from the source")
    try:
        with target.connect() as conn:
            _require_pg18_server(conn)
            row = conn.execute(
                """SELECT EXISTS (
                    SELECT 1 FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
                      AND n.nspname NOT LIKE 'pg_toast%'
                      AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
                    UNION ALL
                    SELECT 1 FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public'
                    UNION ALL
                    SELECT 1 FROM pg_namespace n
                    WHERE n.nspname NOT IN ('public', 'pg_catalog', 'information_schema')
                      AND n.nspname NOT LIKE 'pg_toast%'
                    UNION ALL
                    SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql'
                )"""
            ).fetchone()
            if row is None:
                raise BackupError("Restore target database check failed")
            has_objects = row[0]
            if has_objects:
                raise BackupError("Restore target database must be empty")
    except psycopg.Error as exc:
        raise BackupError("Restore target database check failed") from exc
    _run(
        [
            str(executable),
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-acl",
            f"--dbname={target.name}",
            str(dump_path),
        ],
        env=target.process_environment(),
    )
