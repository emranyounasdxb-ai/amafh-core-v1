"""Run an encrypted Drive backup or verify/restore a named set.

This module does not create credentials, keys, schedules, or a Drive connection
until an operator explicitly invokes a subcommand with external configuration.
"""

import argparse
import json
import sys

from app.backup.config import BackupConfig, BackupError
from app.backup.operations import perform_backup, perform_restore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AMAFH Core encrypted backup operations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup", help="Export, encrypt, upload, download-verify, then retain")
    restore = commands.add_parser("restore", help="Verify a specific retained backup set")
    restore.add_argument("--set-id", required=True, help="UUID of the verified backup set")
    restore.add_argument(
        "--apply",
        action="store_true",
        help="Restore to an empty separate target after verification",
    )
    restore.add_argument("--confirm-set-id", help="Repeat the exact set ID when applying a restore")
    args = parser.parse_args(argv)
    try:
        config = BackupConfig.from_environment(restore=args.command == "restore")
        if args.command == "backup":
            backup_result = perform_backup(config)
            output = {
                "setId": backup_result.set_id,
                "verified": backup_result.verified,
                "mediaFiles": backup_result.retained_media_files,
                "expiredVerifiedSetsRemoved": backup_result.expired_sets_removed,
            }
        else:
            restore_result = perform_restore(
                config,
                set_id=args.set_id,
                apply=args.apply,
                confirmation=args.confirm_set_id,
            )
            output = {
                "setId": restore_result.set_id,
                "verified": restore_result.verified,
                "appliedToSeparateTarget": restore_result.applied,
                "mediaFiles": restore_result.retained_media_files,
            }
        print(json.dumps(output, sort_keys=True))
        return 0
    except BackupError as exc:
        print(f"Backup operation failed: {exc}", file=sys.stderr)
        return 1
    except Exception:
        # Library, database, and filesystem exception strings may contain URLs,
        # paths, or provider payloads; never print them from an operator command.
        print("Backup operation failed; no successful result is reported", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
