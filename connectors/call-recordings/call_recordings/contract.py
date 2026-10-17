"""Versioned metadata and streaming contract shared with AMAFH Core.

The browser never sees this contract. AMAFH pulls it over the private connector
API and stores only the catalog fields.
"""

CONTRACT_VERSION = 1

AVAILABILITY = ("pending", "ready", "missing", "unsupported")
SEARCHABLE = "ready"

STATUS_FIELDS = (
    "contractVersion",
    "epoch",
    "processReady",
    "indexReady",
    "phase",
    "lastIndexedAt",
    "journalMin",
    "journalMax",
    "recordingCount",
)

RECORDING_FIELDS = (
    "id",
    "availability",
    "month",
    "customerNumber",
    "extension",
    "filename",
    "byteSize",
    "fileVersion",
    "indexedAt",
    "sequence",
)

# Multi-range requests are refused. A single ``bytes=start-end`` range is served.
# A comma-separated Range header receives 416 and no body.
MULTI_RANGE_STATUS = 416
CURSOR_EXPIRED_STATUS = 410
VERSION_MISMATCH_STATUS = 409
