"""Owner OAuth Google Drive transfer, verification, and scoped retention."""

import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from app.backup.config import BackupConfig, BackupError
from app.backup.crypto import file_digests

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
MIME = "application/octet-stream"
CHUNK = 8 * 1024 * 1024
MARKER = "amafh-core-backup-v1"
_FILE_FIELDS = (
    "id,name,mimeType,parents,trashed,size,md5Checksum,appProperties,owners(emailAddress),driveId"
)


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError
        return parsed
    except (TypeError, ValueError) as exc:
        raise BackupError("Backup set timestamp is invalid") from exc


def _name(set_id: str) -> str:
    return f"amafh-core-{set_id}.amafhbk"


class DriveStore:
    def __init__(self, config: BackupConfig):
        self.config = config
        try:
            credentials = Credentials.from_authorized_user_file(
                str(config.oauth_file), scopes=[DRIVE_SCOPE]
            )
            if not credentials.refresh_token:
                raise ValueError
            credentials.refresh(Request())
            self.service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        except Exception as exc:
            raise BackupError("Owner Google Drive authentication failed") from exc
        self._check_owner_folder()

    @staticmethod
    def _execute(request: object) -> dict:
        try:
            return request.execute(num_retries=3)  # type: ignore[attr-defined, no-any-return]
        except Exception as exc:
            raise BackupError("Google Drive request failed") from exc

    def _owner_only(self, file_id: str) -> None:
        permissions = []
        token = None
        while True:
            response = self._execute(
                self.service.permissions().list(
                    fileId=file_id,
                    fields="nextPageToken,permissions(id,type,role,emailAddress)",
                    pageSize=1000,
                    pageToken=token,
                    supportsAllDrives=False,
                )
            )
            permissions.extend(response.get("permissions", []))
            token = response.get("nextPageToken")
            if not token:
                break
        if len(permissions) != 1 or not (
            permissions[0].get("type") == "user"
            and permissions[0].get("role") == "owner"
            and permissions[0].get("emailAddress", "").casefold() == self.config.owner_email
        ):
            raise BackupError("Google Drive destination is not Owner-only")

    def _check_owner_folder(self) -> None:
        about = self._execute(self.service.about().get(fields="user(emailAddress)"))
        if about.get("user", {}).get("emailAddress", "").casefold() != self.config.owner_email:
            raise BackupError("Google Drive account does not match the configured Owner")
        folder = self._execute(
            self.service.files().get(
                fileId=self.config.drive_folder_id,
                fields="id,mimeType,trashed,driveId,owners(emailAddress),capabilities(canAddChildren)",
            )
        )
        if not (
            folder.get("id") == self.config.drive_folder_id
            and folder.get("mimeType") == "application/vnd.google-apps.folder"
            and not folder.get("trashed")
            and not folder.get("driveId")
            and folder.get("capabilities", {}).get("canAddChildren")
            and [x.get("emailAddress", "").casefold() for x in folder.get("owners", [])]
            == [self.config.owner_email]
        ):
            raise BackupError("Google Drive destination folder is not Owner-owned")
        self._owner_only(self.config.drive_folder_id)

    def _metadata(self, file_id: str) -> dict:
        return self._execute(self.service.files().get(fileId=file_id, fields=_FILE_FIELDS))

    def _validate_file(
        self, item: dict, set_id: str, *, state: str, require_current_key: bool = True
    ) -> dict:
        properties = item.get("appProperties") or {}
        if not (
            item.get("name") == _name(set_id)
            and item.get("mimeType") == MIME
            and not item.get("trashed")
            and not item.get("driveId")
            and item.get("parents") == [self.config.drive_folder_id]
            and [x.get("emailAddress", "").casefold() for x in item.get("owners", [])]
            == [self.config.owner_email]
            and properties.get("marker") == MARKER
            and properties.get("setId") == set_id
            and properties.get("state") == state
            and isinstance(properties.get("sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", properties["sha256"])
            and isinstance(properties.get("keyId"), str)
            and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", properties["keyId"])
            and (not require_current_key or properties["keyId"] == self.config.key_id)
            and isinstance(properties.get("createdAt"), str)
        ):
            raise BackupError("Google Drive backup identity or scope is invalid")
        _utc(properties["createdAt"])
        if state == "verified":
            verified_at = properties.get("verifiedAt")
            if not isinstance(verified_at, str) or _utc(verified_at) < _utc(
                properties["createdAt"]
            ):
                raise BackupError("Verified backup evidence is missing")
        self._owner_only(item["id"])
        return properties

    def upload_pending(
        self, encrypted_path: Path, *, set_id: str, created_at: str, sha256: str
    ) -> str:
        body = {
            "name": _name(set_id),
            "mimeType": MIME,
            "parents": [self.config.drive_folder_id],
            "appProperties": {
                "marker": MARKER,
                "setId": set_id,
                "state": "pending",
                "sha256": sha256,
                "keyId": self.config.key_id,
                "createdAt": created_at,
            },
        }
        media = MediaFileUpload(str(encrypted_path), mimetype=MIME, chunksize=CHUNK, resumable=True)
        try:
            request = self.service.files().create(body=body, media_body=media, fields="id")
            result = None
            while result is None:
                _, result = request.next_chunk(num_retries=3)
            if not result.get("id"):
                raise BackupError("Google Drive upload returned no file identity")
            return str(result["id"])
        except BackupError:
            raise
        except Exception as exc:
            raise BackupError("Google Drive backup upload failed") from exc
        finally:
            media.stream().close()

    def download(self, file_id: str, output_path: Path) -> None:
        descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as output:
                downloader = MediaIoBaseDownload(
                    output, self.service.files().get_media(fileId=file_id), chunksize=CHUNK
                )
                done = False
                while not done:
                    _, done = downloader.next_chunk(num_retries=3)
                output.flush()
                os.fsync(output.fileno())
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise BackupError("Google Drive backup download failed") from exc

    def downloaded_file(
        self, file_id: str, set_id: str, output_path: Path, *, state: str
    ) -> tuple[dict, dict]:
        item = self._metadata(file_id)
        properties = self._validate_file(item, set_id, state=state)
        self.download(file_id, output_path)
        size, sha256, md5 = file_digests(output_path)
        if (
            sha256 != properties["sha256"]
            or str(size) != item.get("size")
            or md5 != item.get("md5Checksum")
        ):
            raise BackupError("Downloaded backup does not match Google Drive metadata")
        return item, properties

    def mark_verified(self, file_id: str, set_id: str, created_at: str, sha256: str) -> None:
        current = self._metadata(file_id)
        properties = self._validate_file(current, set_id, state="pending")
        if properties["createdAt"] != created_at or properties["sha256"] != sha256:
            raise BackupError("Uploaded backup metadata changed before verification")
        verified = {**properties, "state": "verified", "verifiedAt": datetime.now(UTC).isoformat()}
        self._execute(self.service.files().update(fileId=file_id, body={"appProperties": verified}))
        final = self._metadata(file_id)
        final_properties = self._validate_file(final, set_id, state="verified")
        if final_properties != verified:
            raise BackupError("Google Drive did not retain verified backup status")

    def _list(self, query: str) -> list[dict]:
        results = []
        token = None
        while True:
            response = self._execute(
                self.service.files().list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken,files(" + _FILE_FIELDS + ")",
                    pageSize=1000,
                    pageToken=token,
                )
            )
            results.extend(response.get("files", []))
            token = response.get("nextPageToken")
            if not token:
                return results

    def find_verified(self, set_id: str) -> dict:
        UUID(set_id)
        query = (
            f"'{self.config.drive_folder_id}' in parents and trashed = false "
            f"and appProperties has {{ key='marker' and value='{MARKER}' }} "
            f"and appProperties has {{ key='setId' and value='{set_id}' }} "
            "and appProperties has { key='state' and value='verified' }"
        )
        matches = self._list(query)
        if len(matches) != 1:
            raise BackupError("Verified backup set was not found uniquely")
        self._validate_file(matches[0], set_id, state="verified")
        return matches[0]

    def retain_recent_verified(self, *, new_set_id: str, now: datetime) -> int:
        cutoff = now - timedelta(days=10)
        query = (
            f"'{self.config.drive_folder_id}' in parents and trashed = false "
            f"and appProperties has {{ key='marker' and value='{MARKER}' }} "
            "and appProperties has { key='state' and value='verified' }"
        )
        removed = 0
        for item in self._list(query):
            properties = item.get("appProperties") or {}
            set_id = properties.get("setId", "")
            try:
                UUID(set_id)
            except (TypeError, ValueError) as exc:
                raise BackupError("Verified application backup has an invalid set ID") from exc
            self._validate_file(item, set_id, state="verified", require_current_key=False)
            if set_id == new_set_id or _utc(properties["createdAt"]) >= cutoff:
                continue
            # Re-read immediately before permanent deletion. A stale list result
            # or a moved/retagged file cannot broaden this deletion boundary.
            current = self._metadata(item["id"])
            current_properties = self._validate_file(
                current, set_id, state="verified", require_current_key=False
            )
            if _utc(current_properties["createdAt"]) >= cutoff:
                continue
            self._execute(self.service.files().delete(fileId=item["id"]))
            removed += 1
        return removed
