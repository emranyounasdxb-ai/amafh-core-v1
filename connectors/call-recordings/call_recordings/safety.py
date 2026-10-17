"""Read-only open path that trusts the final file handle, not the string checked earlier."""

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes
from pathlib import Path

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_BEGIN = 0
INVALID_HANDLE = ctypes.c_void_p(-1).value
ERROR_SHARING_VIOLATION = 32
ERROR_LOCK_VIOLATION = 33


class SourceUnsafe(Exception):
    """The path is not a readable file inside the fixed root."""


class SourcePending(Exception):
    """The file exists but is locked, partial, or not yet safe to index."""


class SourceChanged(Exception):
    """The opened handle is not the version the caller asked to read."""


_OPEN_STREAMS = 0
_OPEN_LOCK = threading.Lock()


def open_stream_count() -> int:
    with _OPEN_LOCK:
        return _OPEN_STREAMS


def _account_open(delta: int) -> None:
    global _OPEN_STREAMS
    with _OPEN_LOCK:
        _OPEN_STREAMS += delta


class _FileTime(ctypes.Structure):
    _fields_ = (("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD))


class _ByHandle(ctypes.Structure):
    _fields_ = (
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", _FileTime),
        ("ftLastAccessTime", _FileTime),
        ("ftLastWriteTime", _FileTime),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    )


def _kernel32():
    if sys.platform != "win32":
        raise SourceUnsafe("The recording connector reads files on Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ByHandle)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel.ReadFile.restype = wintypes.BOOL
    kernel.SetFilePointerEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_longlong,
        ctypes.POINTER(ctypes.c_longlong),
        wintypes.DWORD,
    ]
    kernel.SetFilePointerEx.restype = wintypes.BOOL
    return kernel


_KERNEL = None


def kernel32():
    global _KERNEL
    if _KERNEL is None:
        _KERNEL = _kernel32()
    return _KERNEL


def single_component(name: str) -> bool:
    if not isinstance(name, str) or not name or name in {".", ".."}:
        return False
    if any(character in name for character in "/\\:\0"):
        return False
    if name.endswith((" ", ".")):
        return False
    return True


def assert_local_root(path: Path) -> Path:
    """Refuse UNC, device, and reparse roots. The archive is read in place."""
    if sys.platform != "win32":
        raise SourceUnsafe("The recording connector reads files on Windows")
    text = str(path)
    if text.startswith("\\\\") or text.startswith("//") or text.startswith("\\\\.\\"):
        raise SourceUnsafe("UNC and device paths are not a recording root")
    resolved = path.resolve(strict=False)
    if not resolved.exists() or not resolved.is_dir():
        raise SourceUnsafe("Recording root is not a directory")
    handle = open_handle(resolved, directory=True)
    try:
        info = file_info(handle)
        if info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
            raise SourceUnsafe("Recording root is a reparse point")
        if not info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY:
            raise SourceUnsafe("Recording root is not a directory")
        return Path(final_path(handle))
    finally:
        close_handle(handle)


def candidate(root: Path, month: str, filename: str) -> Path:
    if not single_component(month) or not single_component(filename):
        raise SourceUnsafe("Recording name is not a single path component")
    child = root.joinpath(month, filename)
    try:
        relative = child.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise SourceUnsafe("Recording path escapes the root") from exc
    if relative.parts != (month, filename):
        raise SourceUnsafe("Recording path is not a direct monthly file")
    return child


class OpenedFile:
    def __init__(self, handle, info: _ByHandle, final: str, size: int, version: str):
        self.handle = handle
        self.info = info
        self.final = final
        self.size = size
        self.version = version
        self._closed = False
        self._accounted = True
        _account_open(1)

    def _require_same_version(self) -> None:
        info = file_info(self.handle)
        size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
        if not constant_same(file_version(info, size), self.version):
            raise SourceChanged("File version changed")

    def read_at(self, offset: int, length: int) -> bytes:
        if self._closed:
            raise SourceUnsafe("File handle is closed")
        self._require_same_version()
        if offset < 0 or length < 0 or offset > self.size:
            raise SourceUnsafe("Read is outside the file")
        length = min(length, self.size - offset)
        if length == 0:
            return b""
        new_pos = ctypes.c_longlong()
        if not kernel32().SetFilePointerEx(self.handle, offset, ctypes.byref(new_pos), FILE_BEGIN):
            raise SourcePending("File could not be read")
        remaining = length
        chunks = []
        while remaining:
            step = min(remaining, 65536)
            buffer = ctypes.create_string_buffer(step)
            read = wintypes.DWORD()
            ok = kernel32().ReadFile(
                self.handle, buffer, step, ctypes.byref(read), None
            )
            if not ok:
                raise SourcePending("File could not be read")
            if read.value == 0:
                break
            chunks.append(buffer.raw[: read.value])
            remaining -= read.value
        self._require_same_version()
        return b"".join(chunks)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            close_handle(self.handle)
        finally:
            if self._accounted:
                self._accounted = False
                _account_open(-1)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def open_checked(root_final: str, path: Path, *, expect_version: str | None = None) -> OpenedFile:
    handle = open_handle(path, directory=False)
    try:
        info = file_info(handle)
        if info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY):
            raise SourceUnsafe("Recording is a directory or reparse point")
        final = final_path(handle)
        if not within_root(root_final, final):
            raise SourceUnsafe("Opened handle is outside the recording root")
        size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
        version = file_version(info, size)
        if expect_version is not None and not constant_same(version, expect_version):
            raise SourceChanged("File version changed")
        opened = OpenedFile(handle, info, final, size, version)
        handle = None
        return opened
    finally:
        if handle is not None:
            close_handle(handle)


def inspect_header(opened: OpenedFile) -> bytes:
    return opened.read_at(0, 12)


def wav_header_ok(header: bytes) -> bool:
    return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE"


_MAX_WAV_CHUNKS = 64


def wav_payload_complete(opened: OpenedFile) -> bool:
    """True when the RIFF container and its chunk headers fit this file.

    Only chunk headers are read. Audio payload and codec fields are not
    interpreted, so a non-PCM PBX WAV can still be complete.
    """
    if opened.size < 12:
        return False
    header = opened.read_at(0, 12)
    if not wav_header_ok(header):
        return False
    declared = int.from_bytes(header[4:8], "little")
    if declared < 4 or declared + 8 != opened.size:
        return False
    offset = 12
    saw_data = False
    for _ in range(_MAX_WAV_CHUNKS):
        if offset == opened.size:
            return saw_data
        if offset + 8 > opened.size:
            return False
        chunk = opened.read_at(offset, 8)
        if len(chunk) != 8:
            return False
        size = int.from_bytes(chunk[4:8], "little")
        if chunk[:4] == b"data":
            saw_data = True
        step = 8 + size + (size & 1)
        if step < 8 or offset + step > opened.size:
            return False
        offset += step
    return offset == opened.size and saw_data


def open_handle(path: Path, *, directory: bool):
    flags = FILE_FLAG_OPEN_REPARSE_POINT
    if directory:
        flags |= FILE_FLAG_BACKUP_SEMANTICS
    handle = kernel32().CreateFileW(
        str(path),
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        flags,
        None,
    )
    if handle == INVALID_HANDLE or handle is None:
        code = ctypes.get_last_error()
        if code in {ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION}:
            raise SourcePending("File is locked")
        if code in {2, 3}:
            raise SourceUnsafe("File is missing")
        raise SourcePending(f"File could not be opened ({code})")
    return handle


def close_handle(handle) -> None:
    kernel32().CloseHandle(handle)


def file_info(handle) -> _ByHandle:
    info = _ByHandle()
    if not kernel32().GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise SourcePending("File identity could not be read")
    return info


def final_path(handle) -> str:
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel32().GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
    if length == 0 or length >= len(buffer):
        raise SourceUnsafe("Final path could not be read")
    return buffer.value


def within_root(root_final: str, file_final: str) -> bool:
    root = root_final.casefold().rstrip("\\")
    file_text = file_final.casefold()
    if file_text == root:
        return False
    prefix = root + "\\"
    if not file_text.startswith(prefix):
        return False
    relative = file_text[len(prefix) :]
    return relative.count("\\") == 1 and ":" not in relative


def file_identity(path: Path) -> str | None:
    """Volume and file index for one path. Does not read audio or WAV headers."""
    try:
        handle = open_handle(path, directory=False)
    except (SourcePending, SourceUnsafe):
        return None
    try:
        info = file_info(handle)
        if info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY):
            return None
        return f"{info.dwVolumeSerialNumber:x}:{info.nFileIndexHigh:x}:{info.nFileIndexLow:x}"
    except (SourcePending, SourceUnsafe):
        return None
    finally:
        close_handle(handle)


def file_version(info: _ByHandle, size: int) -> str:
    write = (info.ftLastWriteTime.dwHighDateTime << 32) | info.ftLastWriteTime.dwLowDateTime
    return (
        f"{info.dwVolumeSerialNumber:x}:{info.nFileIndexHigh:x}:{info.nFileIndexLow:x}:"
        f"{size}:{write:x}"
    )


def constant_same(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left.encode(), right.encode()) if len(left) == len(right) else False


def directory_is_reparse(path: Path) -> bool:
    try:
        handle = open_handle(path, directory=True)
    except SourcePending:
        return False
    except SourceUnsafe:
        return True
    try:
        info = file_info(handle)
        return bool(info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)
    finally:
        close_handle(handle)
