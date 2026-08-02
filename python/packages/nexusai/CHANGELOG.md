# Changelog

All notable NexusAI changes are recorded here. The project follows semantic
versioning and the compatibility policy in `COMPATIBILITY.md`.

## 0.1.2

- Fixed `nexusai login` to use the current default CAS URL unless `--cas-url`
  is explicitly supplied.

## 0.1.1

- Changed the default Platform API and CAS URLs to the `ric1` environment.

## 0.1.0

- Added typed public Summary, Detail, Action, Monitoring, Page, Upload, and
  Download result models.
- Removed transport-oriented RPC client names from public imports.
- Removed workload-only clients and internal lifecycle records from the public
  client surface.
- Moved HTTP, CAS storage exchange, and object-transfer implementations under
  `nexusai._internal`; public transfer files contain only relative paths and
  byte sizes.
- Added table-first CLI output, JSON and scalar modes, stable error tables, and
  documented exit codes.
- Added bounded retry policy with automatic stable idempotency headers for
  mutation retries.
- Added training and inference waiters.
- Added atomic, size-verified downloads and upload symlink/path protections.
- Preserved response pagination and request metadata.
- Added typed package metadata and the `py.typed` marker.
