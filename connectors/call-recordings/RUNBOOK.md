# Call recording connector

The connector reads original recordings in place. It does not copy, move, rename, edit, or delete them. Its index, token, and logs stay in a separate state directory.

## Local console

1. Create a state directory outside the recording root.
2. Write a random token of at least 16 characters into the token file. Do not commit it.
3. Copy `config.example.toml`, point `source_root` at a synthetic directory for local work, and set `state_directory`, `token_file`, and `bind_host` to `127.0.0.1`.
4. From `connectors/call-recordings`, run:

```
python -m call_recordings serve --config connector.toml
```

The process listens only on the configured address. `0.0.0.0` is refused. Readiness is `phase=indexing` until one complete reconciliation succeeds, then `phase=ready`. Restart keeps the SQLite index and epoch.

SQLite uses rollback-journal mode. Do not enable WAL on SQLite 3.50.4, and do not put the database on a network share.

## Windows service source

`call_recordings.service.CallRecordingWindowsService` is the importable Service Control Manager class. It is published on the module when `windows_service_class()` runs, and again at import when pywin32 is installed. `windows/install-service.ps1 -Python <python> -Config <toml>` passes that config path. The service command stores it as the `ConfigFile` custom option, and `SvcDoRun` reads that option. `uninstall` is sent to pywin32 as `remove`. Stop and removal failures return a non-zero exit code.

Application-only install, from `connectors/call-recordings`, when that machine is authorized to register the service:

```
python -m pip install ".[service]"
```

`requirements-service.txt` pins `pywin32==311`. This workspace did not download, hash-lock, or install that package, and it did not register a service.

This workspace verified console start and stop, plus local handler tests that do not contact the Service Control Manager. It did not install a Windows service and did not verify Windows Server 2022.

The shipped watcher polls directory modification times every half second and passes changed month names as a hint. Reconciliation remains the authority. Ready files whose size and modification time are unchanged are not opened again. A pass opens at most a bounded batch and resumes from a stored checkpoint. A month that was not listed is not marked missing. This is not a verified ReadDirectoryChangesW or FileSystemWatcher installation on Windows Server 2022.

Shutdown stops the scanner before closing SQLite. If the scanner thread is still running, the index stays open. Open file handles are counted and waited on; any that remain are recorded on the process object. Console shutdown was checked locally. Service Control Manager installation was not.

## Private API

All routes require `Authorization: Bearer` and the token file. There is no path parameter.

- `GET /v1/catalog/status`
- `GET /v1/catalog/changes?after=<sequence>&limit=<1-500>`
- `GET /v1/catalog/snapshot?cursor=<id>&limit=<1-500>`
- `GET` and `HEAD /v1/recordings/<id>/content` with `X-AMAFH-File-Version`. HEAD returns length and validators and does not read the audio body.

A comma-separated Range is `416`. One byte range is `206`. A changed file version is `409` and the new bytes are not sent. An expired change cursor is `410`; the caller must take a snapshot. The previous searchable catalog stays in place until that snapshot is published by AMAFH.
