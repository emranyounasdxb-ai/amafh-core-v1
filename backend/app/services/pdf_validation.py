"""PDF parsing in killable, bounded child processes; never on the API event loop."""

import asyncio
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from app.errors import ApiError

MAX_PDF_BYTES = 5_000_000
PDF_DEADLINE_SECONDS = 5.0
MAX_PDF_WORKERS = 2
_admission = threading.BoundedSemaphore(MAX_PDF_WORKERS)


def _parse(data: bytes) -> None:
    import io

    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    from pypdf.generic import DictionaryObject, NullObject, StreamObject

    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted and not reader.decrypt(""):
        raise PdfReadError("PDF requires a password")
    root = reader.root_object
    pages = root.get("/Pages")
    if root.get("/Type") != "/Catalog" or pages is None:
        raise PdfReadError("Invalid PDF catalog")
    tree = pages.get_object()
    if not isinstance(tree, DictionaryObject) or tree.get("/Type") != "/Pages":
        raise PdfReadError("Invalid PDF page tree")
    for page in reader.pages:
        if page.get("/Type") != "/Page" or len(page.mediabox) != 4:
            raise PdfReadError("Invalid PDF page")
        contents = page.get("/Contents")
        if contents is not None:
            resolved = contents.get_object()
            if isinstance(resolved, NullObject):
                continue
            objects = resolved if isinstance(resolved, list) else [resolved]
            if any(not isinstance(item.get_object(), StreamObject) for item in objects):
                raise PdfReadError("Invalid PDF content stream")


def _worker() -> int:
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (4, 4))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    data = sys.stdin.buffer.read(MAX_PDF_BYTES + 1)
    if not data or len(data) > MAX_PDF_BYTES:
        return 2
    try:
        _parse(data)
    except Exception:
        return 2
    return 0


def _run(data: bytes, cancelled: threading.Event) -> int:
    process = None
    deadline = time.monotonic() + PDF_DEADLINE_SECONDS
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.services.pdf_validation", "--worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).resolve().parents[2],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        pending: bytes | None = data
        while not cancelled.is_set() and time.monotonic() < deadline:
            try:
                process.communicate(
                    input=pending, timeout=min(0.1, max(0.001, deadline - time.monotonic()))
                )
                return process.returncode
            except subprocess.TimeoutExpired:
                pending = None
        return -1
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.communicate()
            process.wait()
        # Admission is released only after termination, including cancellation.
        _admission.release()


async def validate_pdf(data: bytes) -> None:
    if len(data) > MAX_PDF_BYTES:
        raise ApiError(422, "DOCUMENT_SIZE_LIMIT", "File exceeds 5,000,000 bytes")
    if not _admission.acquire(blocking=False):
        raise ApiError(
            429, "DOCUMENT_VALIDATION_BUSY", "Document validation is busy. Retry shortly."
        )
    cancelled = threading.Event()
    runner = asyncio.create_task(asyncio.to_thread(_run, data, cancelled))
    try:
        result = await asyncio.shield(runner)
    except asyncio.CancelledError:
        cancelled.set()
        await asyncio.shield(runner)
        raise
    except OSError as exc:
        raise ApiError(
            503, "DOCUMENT_VALIDATION_UNAVAILABLE", "Document validation is unavailable"
        ) from exc
    if result == -1:
        raise ApiError(422, "DOCUMENT_COMPLEXITY_LIMIT", "PDF exceeds the safe processing limit")
    if result != 0:
        raise ApiError(
            422, "DOCUMENT_INVALID", "PDF content is invalid or exceeds the safe processing limit"
        )


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        sys.exit(2)
    sys.exit(_worker())
