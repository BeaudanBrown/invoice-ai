# Control-Plane Store

`invoice-ai` now has a local SQLite-backed metadata store at:

- `/var/lib/invoice-ai/control-plane.sqlite3`

## Purpose

This store is the queryable metadata layer for the control plane. It exists alongside:

- `ERPNext` for canonical business truth
- filesystem artifacts for human-readable reviews, previews, ingest records, and memory documents

It is not a replacement for either.

## Current Tables

- `requests`
  - one row per top-level CLI or HTTP tool execution
- `jobs`
  - one row per top-level execution job
- `job_events`
  - append-only execution events
- `idempotency_keys`
  - stored result fingerprints for ERP write-style requests
- `reviews`
  - approval and review metadata
- `review_actions`
  - accept/reject actions taken against reviews
- `artifacts`
  - indexed filesystem artifacts such as approval files and preview PDFs
- `ingest_index`
  - cross-reference metadata for ingest records and linked ERP refs
- `memory_suggestions`
  - indexed memory-review suggestions and their current status

## Current Write Sources

The database is currently populated by:

- the shared tool execution path used by the CLI and HTTP service
- approval artifact writes
- ingest record writes
- quotation revision writes
- memory suggestion and review actions

## Deliberate Limits

The current store does not yet:

- enforce request authentication
- expose a formal query API
- manage background jobs beyond the current synchronous job ledger
- replace the filesystem as the primary storage for bulky artifacts

Those are follow-on hardening steps. The point of this slice is to make the control plane durable and queryable before the FastAPI/auth migration.
