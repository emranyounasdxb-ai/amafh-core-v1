"""python -m call_recordings serve --config connector.toml"""

import argparse
from pathlib import Path

from .app import serve
from .service import service_command


def main() -> None:
    parser = argparse.ArgumentParser(description="AMAFH call-recording connector")
    sub = parser.add_subparsers(dest="command", required=True)
    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--config", required=True, type=Path)
    service_parser = sub.add_parser("service")
    service_parser.add_argument("action", choices=("install", "uninstall", "start", "stop"))
    service_parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.command == "serve":
        serve(args.config)
        return
    command = [args.action]
    if args.config is not None:
        command.extend(["--config", str(args.config)])
    service_command(command)


if __name__ == "__main__":
    main()
