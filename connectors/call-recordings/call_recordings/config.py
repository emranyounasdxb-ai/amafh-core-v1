"""Connector configuration. Secrets stay in a token file, never in the archive."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .safety import SourceUnsafe, assert_local_root


@dataclass(frozen=True)
class ConnectorConfig:
    source_root: Path
    root_final: str
    state_directory: Path
    bind_host: str
    bind_port: int
    token: str
    settle_seconds: float
    reconcile_seconds: float
    journal_keep: int


def load_config(path: Path) -> ConnectorConfig:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    source = Path(str(data["source_root"]))
    state = Path(str(data["state_directory"]))
    host = str(data.get("bind_host", "127.0.0.1")).strip()
    port = int(data.get("bind_port", 8765))
    if host in {"", "0.0.0.0", "::", "[::]"}:
        raise ValueError("The connector refuses a public wildcard bind")
    if not 1 <= port <= 65535:
        raise ValueError("bind_port is not a valid port")
    token_file = Path(str(data["token_file"]))
    _refuse_inside(source, state)
    _refuse_inside(source, token_file)
    token = token_file.read_text(encoding="utf-8").strip()
    if len(token) < 16 or any(character in token for character in "\r\n\0"):
        raise ValueError("Connector token file is unusable")
    try:
        root_final = str(assert_local_root(source))
    except SourceUnsafe as exc:
        raise ValueError(str(exc)) from exc
    state.mkdir(parents=True, exist_ok=True)
    protect_state(state)
    return ConnectorConfig(
        source_root=source,
        root_final=root_final,
        state_directory=state,
        bind_host=host,
        bind_port=port,
        token=token,
        settle_seconds=float(data.get("settle_seconds", 2)),
        reconcile_seconds=float(data.get("reconcile_seconds", 300)),
        journal_keep=int(data.get("journal_keep", 50_000)),
    )


def _refuse_inside(root: Path, other: Path) -> None:
    root_text = str(root.resolve(strict=False)).casefold().rstrip("\\")
    other_text = str(other.resolve(strict=False)).casefold()
    if other_text == root_text or other_text.startswith(root_text + "\\"):
        raise ValueError("Operational state must stay outside the recording archive")


def protect_state(directory: Path) -> None:
    """Restrict the state directory to the current user. The archive is not touched."""
    if os.name != "nt":
        return
    import subprocess

    identified = subprocess.run(
        ["whoami"],
        check=False,
        capture_output=True,
        text=True,
    )
    user = identified.stdout.strip()
    if identified.returncode != 0 or not user or any(character in user for character in "\r\n\0"):
        raise RuntimeError("The current Windows user could not be identified")
    protected = subprocess.run(
        ["icacls", str(directory), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"],
        check=False,
        capture_output=True,
        text=True,
    )
    if protected.returncode != 0:
        raise RuntimeError("The connector state directory could not be protected")
