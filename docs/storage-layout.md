# Storage Layout

This document defines the first persistent storage layout under:

- `/var/lib/invoice-ai/`

The purpose of this layout is to keep mutable operational state out of git while making the NixOS module contract explicit and stable.

## Design Rules

1. Structured ERP truth lives in `ERPNext`, not in this directory.
2. This directory stores agent-owned mutable state:
   - markdown memory
   - review and approval artifacts
   - ingestion source material
   - working revision snapshots
   - SQLite-backed control-plane metadata
3. The layout should be auditable and human-readable where practical.
4. The layout should avoid excessive retention of noisy transient artifacts.

## Top-Level Layout

Recommended top-level directories:

- `/var/lib/invoice-ai/control-plane.sqlite3`
- `/var/lib/invoice-ai/memory`
- `/var/lib/invoice-ai/ingest`
- `/var/lib/invoice-ai/approvals`
- `/var/lib/invoice-ai/revisions`
- `/var/lib/invoice-ai/artifacts`
- `/var/lib/invoice-ai/jobs`
- `/var/lib/invoice-ai/events`
- `/var/lib/invoice-ai/cache`

## Control-Plane Store

Path:

- `/var/lib/invoice-ai/control-plane.sqlite3`

Purpose:

- keep local operational metadata queryable without turning the filesystem tree into the only index

Examples:

- request ids
- job state
- job events
- review records and actions
- idempotency keys
- artifact indexes
- ingest indexes
- memory suggestion indexes

Current implementation:

- populated from the shared CLI/HTTP execution path
- indexes approval writes, memory review actions, ingest records, quotation preview artifacts, and ERP write idempotency fingerprints
- documented further in `docs/control-plane-store.md`

Retention policy:

- durable by default
- backed up with the rest of `/var/lib/invoice-ai`
- compacted deliberately rather than implicitly

## Memory

Path:

- `/var/lib/invoice-ai/memory`

Recommended subdirectories:

- `operator/`
- `clients/`
- `jobs/`
- `global/`

Recommended file shape:

- markdown files with lightweight frontmatter or stable headings
- one logical memory document per subject

Examples:

- `clients/acme-electrical.md`
- `jobs/smith-switchboard-upgrade.md`
- `operator/pricing-preferences.md`

Retention policy:

- long-lived
- versioned by normal app behavior or filesystem backup, not by chat transcript dumps
- updated in place when the semantic instruction remains current

## Ingest

Path:

- `/var/lib/invoice-ai/ingest`

Recommended subdirectories:

- `incoming/`
- `processed/`
- `rejected/`

Recommended per-ingest record layout:

- original file or captured source material
- extracted structured payload
- normalization result
- ERP target proposal

Example:

- `/var/lib/invoice-ai/ingest/processed/2026/03/23/<ingest-id>/source.pdf`
- `/var/lib/invoice-ai/ingest/processed/2026/03/23/<ingest-id>/extracted.json`
- `/var/lib/invoice-ai/ingest/processed/2026/03/23/<ingest-id>/proposal.json`

Retention policy:

- keep original source and final extracted/proposed forms for audit and reprocessing
- move unusable ingests to `rejected/` with an error summary rather than deleting them immediately

## Approvals

Path:

- `/var/lib/invoice-ai/approvals`

Purpose:

- hold approval-gated action requests and their supporting material

Recommended per-approval layout:

- `request.json`
- `summary.md`
- `diff.json`
- linked preview artifacts when relevant

Example:

- `/var/lib/invoice-ai/approvals/<approval-id>/request.json`
- `/var/lib/invoice-ai/approvals/<approval-id>/summary.md`
- `/var/lib/invoice-ai/approvals/<approval-id>/diff.json`

Retention policy:

- preserve for audit
- do not delete automatically just because the approval was granted or rejected

## Revisions

Path:

- `/var/lib/invoice-ai/revisions`

Purpose:

- keep working snapshots of quote/invoice drafts outside ERPNext so conversational iteration does not flood ERP history

Recommended grouping:

- `quotations/<draft-key>/`
- `sales-invoices/<draft-key>/`

Recommended per-revision files:

- `revision-<n>.json`
- optional rendered preview
- metadata linking the revision to ERP doctype and document name if one exists

Retention policy:

- keep active working revisions while a document remains in draft
- once the document is submitted or abandoned, compact transient revisions
- keep enough history to explain recent changes, but do not preserve every trivial conversational tweak forever

## Artifacts

Path:

- `/var/lib/invoice-ai/artifacts`

Purpose:

- store operator-facing generated files such as PDFs and structured exports

Recommended grouping:

- `quotes/`
- `invoices/`
- `comparisons/`

Examples:

- generated quote PDFs
- generated invoice PDFs
- comparison sheets used during review

Retention policy:

- keep the latest approved or operator-visible artifacts
- superseded previews may be compacted if the corresponding revision snapshot still exists

## Jobs

Path:

- `/var/lib/invoice-ai/jobs`

Purpose:

- persist long-running or replayable control-plane work units

Examples:

- supplier-document processing jobs
- quote/invoice drafting jobs
- review-action jobs

Retention policy:

- keep recent job metadata and terminal state for audit and debugging
- allow old completed jobs to be compacted once their linked artifacts and ERP refs remain discoverable

## Events

Path:

- `/var/lib/invoice-ai/events`

Purpose:

- store append-only audit-style event records for the operator control plane

Examples:

- request accepted
- planner produced operator request
- ERP mutation attempted
- approval created
- review accepted or rejected

Retention policy:

- preserve as the main local audit trail
- rotate by size or age only with an explicit retention policy

## Cache

Path:

- `/var/lib/invoice-ai/cache`

Purpose:

- non-authoritative scratch output that can be safely rebuilt

Examples:

- temporary extraction intermediates
- model prompt caches
- downloaded remote content pending normalization

Retention policy:

- short-lived
- safe to clear

## NixOS Module Implications

The NixOS module should expose `stateDir` as the root and provide stable defaults for:

- control-plane store path
- memory directory
- ingest directory
- approvals directory
- revisions directory
- artifacts directory
- jobs directory
- events directory
- cache directory

Host-specific backup and filesystem choices should remain in `nix-dotfiles`.
