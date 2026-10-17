"""Windows Service adapter.

Console mode is the local entry point. Service registration uses pywin32 when
that package is installed for a later authorized Windows Server setup. This
module does not register, start, or stop a Service Control Manager service
unless its install command is invoked explicitly. Local tests pass a handler
and never contact the real Service Control Manager.
"""

from __future__ import annotations

from pathlib import Path

SERVICE_NAME = "AMAFHCallRecordings"
SERVICE_DISPLAY = "AMAFH Call Recordings"
SERVICE_DESCRIPTION = "Read-only index and private stream of PBX call recordings."
_ACTIONS = {
    "install": "install",
    "uninstall": "remove",
    "remove": "remove",
    "start": "start",
    "stop": "stop",
    "debug": "debug",
}


class ServiceAdapter:
    """The body a Windows Service would run. Tests call this without installing anything."""

    def __init__(self, config_path: Path):
        from .app import ConnectorApp
        from .config import load_config

        self.app = ConnectorApp(load_config(config_path))

    def run(self) -> None:
        self.app.start()
        try:
            self.app.wait_until_stopped()
        finally:
            self.app.stop()

    def request_stop(self) -> None:
        self.app.request_stop()


def pywin32_available() -> bool:
    try:
        import win32serviceutil  # noqa: F401
    except ImportError:
        return False
    return True


def load_registered_config() -> str:
    """Read the config path stored when the service was installed."""
    import win32serviceutil

    value = win32serviceutil.GetServiceCustomOption(SERVICE_NAME, "ConfigFile", None)
    if not value:
        raise RuntimeError("Service ConfigFile is not registered. Install with --config.")
    return str(value)


def remember_config(path: str, options: dict | None = None) -> None:
    if options is not None:
        options["ConfigFile"] = path
        return
    import win32serviceutil

    win32serviceutil.SetServiceCustomOption(SERVICE_NAME, "ConfigFile", path)


def windows_service_class():
    """Publish the Service Control Manager class on this module.

    pywin32 imports ``module.ClassName`` when the service starts. The class
    statement inside this function is assigned to the module so that lookup
    succeeds. When pywin32 is already installed, import time publishes it too.
    """
    existing = globals().get("CallRecordingWindowsService")
    if isinstance(existing, type) and existing.__dict__.get("_svc_name_") == SERVICE_NAME:
        return existing
    global win32event, win32service, win32serviceutil
    import win32event
    import win32service
    import win32serviceutil

    class CallRecordingWindowsService(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args):
            base = win32serviceutil.ServiceFramework
            if base is not object:
                base.__init__(self, args)
            self.adapter: ServiceAdapter | None = None
            self.stop_event = None
            creator = getattr(win32event, "CreateEvent", None)
            if base is not object and callable(creator):
                self.stop_event = creator(None, 0, 0, None)

        def _report(self, state: int) -> None:
            report = getattr(win32serviceutil.ServiceFramework, "ReportServiceStatus", None)
            if callable(report):
                report(self, state)

        def SvcStop(self):
            pending = getattr(win32service, "SERVICE_STOP_PENDING", None)
            if pending is not None:
                self._report(pending)
            if self.adapter is not None:
                self.adapter.request_stop()
            setter = getattr(win32event, "SetEvent", None)
            if callable(setter) and self.stop_event is not None:
                setter(self.stop_event)

        def SvcDoRun(self):
            running = getattr(win32service, "SERVICE_RUNNING", None)
            if running is not None:
                self._report(running)
            self.adapter = ServiceAdapter(Path(load_registered_config()))
            try:
                self.adapter.run()
            finally:
                self.adapter = None

    CallRecordingWindowsService.__module__ = __name__
    globals()["CallRecordingWindowsService"] = CallRecordingWindowsService
    return CallRecordingWindowsService


def _parse_service_args(argv: list[str]) -> tuple[str, str | None]:
    if not argv:
        raise SystemExit(
            "Usage: python -m call_recordings service install|uninstall|start|stop --config PATH"
        )
    action = argv[0].lower()
    config = None
    index = 1
    while index < len(argv):
        item = argv[index]
        if item == "--config" and index + 1 < len(argv):
            config = argv[index + 1]
            index += 2
            continue
        raise SystemExit(
            "Usage: python -m call_recordings service install|uninstall|start|stop --config PATH"
        )
    return action, config


def _default_handler(cls, argv=None):
    if not pywin32_available():
        raise SystemExit(
            "pywin32 is not installed in this environment. "
            "The service adapter source is present, but no service was registered."
        )
    import win32serviceutil

    code = win32serviceutil.HandleCommandLine(cls, argv=list(argv or ["call_recordings"]))
    if isinstance(code, int) and code != 0:
        raise SystemExit(code)
    return code


def service_command(argv: list[str], *, handler=None, options: dict | None = None) -> None:
    """Map install/uninstall/start/stop onto pywin32 without hiding handler errors.

    ``uninstall`` is accepted from the CLI and sent to pywin32 as ``remove``.
    ``options`` captures the config path in tests. The real installer stores it
    with SetServiceCustomOption after a successful install.
    """
    action, config = _parse_service_args(argv)
    mapped = _ACTIONS.get(action)
    if mapped is None:
        raise SystemExit(
            "Usage: python -m call_recordings service install|uninstall|start|stop --config PATH"
        )
    if mapped == "install" and not config:
        raise SystemExit("install requires --config")
    chosen = handler or _default_handler
    result = chosen(windows_service_class(), argv=["call_recordings", mapped])
    if isinstance(result, int) and result != 0:
        raise SystemExit(result)
    if mapped == "install":
        remember_config(str(config), options)
    return result


def install_service(config: str, *, handler=None, options: dict | None = None) -> None:
    service_command(["install", "--config", config], handler=handler, options=options)


if pywin32_available():
    windows_service_class()
