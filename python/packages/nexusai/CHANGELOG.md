# Changelog

All notable NexusAI changes are recorded here. The project follows semantic
versioning and the compatibility policy in `COMPATIBILITY.md`.

## 1.0.1

- Publish model uploads with the complete versioned serving manifest required
  for integrity and inference compatibility checks.
- Added model architecture, runtime, and accelerator options to model upload
  APIs and CLI commands.

## 1.0.0

- Aligned every MLOps client with the public PascalCase RPC surface and strict
  `data`/`items` success envelopes.
- Added typed RFC 7807 problem identifiers and stable lifecycle message-code
  constants.
- Removed legacy success/error envelope decoding and caller-authored request
  IDs.
- Made synchronous delete operations return `None` for `204 No Content` and
  asynchronous deletes return their public lifecycle action.

## 0.1.4

- Keep checkpoint uploads retryable when a post-transfer source validation
  detects an async checkpoint write still in progress.

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
