"""Console process that owns the index, watcher, and private listener."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from .config import ConnectorConfig
from .http_api import RecordingServer
from .index import CatalogIndex
from .scanner import Scanner
from .watcher import Watcher


class ConnectorApp:
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.token = config.token
        self.root = config.source_root
        self.root_final = config.root_final
        self.index = CatalogIndex(
            config.state_directory / "catalog.sqlite",
            journal_keep=config.journal_keep,
        )
        self.scanner: Scanner | None = None
        self.watcher: Watcher | None = None
        self.server: RecordingServer | None = None
        self._http: threading.Thread | None = None
        self._stopped = threading.Event()
        self.unfinished_streams = 0
        self.index_left_open = False

    def start(self) -> None:
        self.index.open()
        self.scanner = Scanner(
            self.index,
            self.root,
            self.root_final,
            settle_seconds=self.config.settle_seconds,
            reconcile_seconds=self.config.reconcile_seconds,
        )
        self.watcher = Watcher(self.root, self.scanner.hint)
        self.server = RecordingServer((self.config.bind_host, self.config.bind_port), self)
        self._http = threading.Thread(target=self.server.serve_forever, name="call-recording-http", daemon=True)
        self._http.start()
        self.watcher.start()
        self.scanner.start()

    def wait_until_stopped(self) -> None:
        self._stopped.wait()

    def request_stop(self) -> None:
        self._stopped.set()

    def stop(self, timeout: float = 20) -> None:
        from .safety import open_stream_count

        self.request_stop()
        scanner_running = False
        if self.scanner is not None:
            self.scanner.stop(timeout=timeout)
            scanner_running = self.scanner.running
        if self.watcher is not None:
            self.watcher.stop(timeout=timeout)
        if self.server is not None:
            shutdown = threading.Thread(target=self.server.shutdown, name="call-recording-shutdown")
            shutdown.start()
            shutdown.join(timeout=5)
            self.server.server_close()
        if self._http is not None:
            self._http.join(timeout=timeout)
        deadline = time.monotonic() + min(timeout, 5)
        while open_stream_count() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.unfinished_streams = open_stream_count()
        self.index_left_open = scanner_running
        if scanner_running:
            return
        self.index.close()

    @property
    def address(self) -> tuple[str, int]:
        if self.server is None:
            return self.config.bind_host, self.config.bind_port
        host, port = self.server.server_address[:2]
        return str(host), int(port)


def serve(config_path: Path) -> None:
    from .config import load_config

    app = ConnectorApp(load_config(config_path))
    app.start()
    try:
        app.wait_until_stopped()
    finally:
        app.stop()
