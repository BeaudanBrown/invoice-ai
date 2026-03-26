# Handoff

## Status

Hardening started on 2026-03-26 after the foundation lane completed its architecture-and-scaffold work.

Inherited completed work:

- packaged flake and NixOS module
- runtime config and persistent path scaffold
- HTTP service and CLI
- ERP semantic tools for the first quotation and purchase-invoice flows
- raw-document extraction, supplier ingest, and composed supplier-document processing
- quote draft and revision orchestration with preview PDFs and local revisions
- planner and orchestrator layers
- markdown memory with review-gated suggestions
- approval artifact persistence and review indexing

## Current Risks

- operator auth is now enforced, but it is still just a token-file boundary with no richer policy or role model
- operator review flows are now complete for the current memory-backed review type, but broader approval classes still need to converge onto the same operator contract
- extraction quality still needs to improve beyond the new anomaly/dedupe/reprocess baseline
- deployment and verification are still mostly mock-driven

## Latest Completed Slice

Completed `coordinator-jdv.1.1` on 2026-03-26.

Highlights:

- standardized the main boundary models around `Pydantic`
- added typed tool envelopes in `src/invoice_ai/erp/schemas.py`
- added typed semantic ERP command payloads in `src/invoice_ai/erp/commands.py`
- added typed operator HTTP models in `src/invoice_ai/service/models.py`
- added typed file-backed persistence records in `src/invoice_ai/persistence.py`
- validated ERP command payloads before side effects
- documented the conventions in `docs/schema-conventions.md`

Verification:

- `nix shell .#python -c python -m compileall src`
- `nix flake check`
- `nix run . -- show-config`
- `nix run . -- run-tool --request-file <memory.list_reviews request>`
- `INVOICE_AI_ERPNEXT_URL=http://127.0.0.1:9999 nix run . -- run-tool --request-file <invalid erp.get_doc request>`
  - confirmed malformed ERP payloads now fail as `validation_error` before any network side effect

## Current Next Action

Use the hardening Beads epic to drive:

1. deployment and end-to-end verification

## Notes

- foundation context remains useful for historical decisions, but active work should anchor on the hardening docs and Beads epic
- the current architectural review is in `docs/architecture-review-2026-03.md`
- the current completion roadmap is in `docs/completion-plan.md`
- the concrete service/store/schema decisions are in `docs/control-plane-hardening.md`
- the live schema conventions are in `docs/schema-conventions.md`

Completed `coordinator-jdv.1.2` on 2026-03-26.

Highlights:

- added the SQLite-backed control-plane store in `src/invoice_ai/control_plane/`
- added the runtime path `control_plane_db_path`
- wired the shared CLI/HTTP execution path to record requests, jobs, events, and ERP-write idempotency fingerprints
- indexed approval artifacts, memory review actions, ingest records, and quote preview artifacts
- documented the store in `docs/control-plane-store.md`

Verification:

- `nix shell .#python -c python -m compileall src`
- `nix flake check`
- temp-state CLI runs confirmed:
  - database creation at `control-plane.sqlite3`
  - request/job/event rows on normal tool execution
  - review and artifact rows on approval-producing memory suggestions
  - review action rows on memory suggestion acceptance
  - idempotency rows on dry-run ERP write-style tools

Completed `coordinator-jdv.1.3` on 2026-03-26.

Highlights:

- replaced the stdlib HTTP shell with a FastAPI app in `src/invoice_ai/service/http.py`
- switched `serve-http` to run on `uvicorn`
- kept the `execute_tool_request()` path as the business boundary
- added dependency-injected runtime state for future auth and background-job hooks
- added `X-Request-ID` middleware and optional `X-Operator-Id` HTTP injection
- exposed OpenAPI/docs routes without changing the core business layer
- updated the flake and module package environments to include `fastapi` and `uvicorn`

Verification:

- `nix shell .#python -c python -m compileall src`
- `nix flake check`
- live temp-state FastAPI probe covering:
  - `GET /healthz`
  - `GET /api/runtime`
  - `POST /api/tools/run`
  - `GET /openapi.json`
  - control-plane `requests.operator_id` recording from `X-Operator-Id`

Completed `coordinator-jdv.2` on 2026-03-26.

Highlights:

- added the new `src/invoice_ai/invoices/` tool family for draft sales-invoice creation and revision
- extended the ERP semantic layer with `erp.create_draft_sales_invoice` and `erp.update_draft_sales_invoice`
- made quote-to-invoice draft creation explicit by letting invoice drafts be grounded in an existing `Quotation`
- added sales-invoice revision snapshots and preview PDF artifacts
- extended the orchestrator and planner with `invoice_draft` and `invoice_revision`
- added planner support for quote-to-invoice turns that reuse `conversation_context.active_quote`

Verification:

- `nix shell .#python -c python -m compileall src`
- mock-ERP temp-state runs covering:
  - direct `invoices.create_draft`
  - `invoices.create_draft` from an existing quotation
  - `invoices.revise_draft`
  - `planner.handle_turn` for quote-to-invoice conversion through the orchestrator

Completed `coordinator-jdv.4` on 2026-03-26.

Highlights:

- added deterministic source fingerprinting for extracted supplier documents
- added extraction anomaly reporting for line-total mismatches and similar document inconsistencies
- added duplicate-ingest checks before unsafe purchase-invoice draft creation
- added `ingest.reprocess_record` so stored ingest records can be replayed through the current pipeline
- fixed ingest index preservation so duplicate checks retain source, supplier, and invoice-reference hints across stage writes

Verification:

- `nix shell .#python -c python -m compileall src`
- temp-state runs covering:
  - extraction anomaly reporting from raw text
  - duplicate detection on repeated `ingest.normalize_supplier_invoice` requests
  - record replay through `ingest.reprocess_record`
  - ingest index metadata carrying source hash, supplier hint, and invoice reference

Completed `coordinator-jdv.1` on 2026-03-26.

Highlights:

- added bearer-token operator auth sourced from `INVOICE_AI_OPERATOR_TOKENS_FILE`
- enforced auth across the `/api/*` FastAPI surface
- exposed authenticated request, job, event, and review inspection endpoints over the SQLite control-plane store
- added typed control-plane query models for request/job/review inspection
- documented the local dev loop for temp-state plus fake-data testing in `docs/dev-testing.md`
- updated the NixOS module so host config can provide the operator token file declaratively

Verification:

- `nix shell .#python -c python -m compileall src`
- `nix flake check`
- live temp-state FastAPI probe covering:
  - `GET /healthz`
  - authenticated `GET /api/runtime`
  - authenticated `POST /api/tools/run`
  - authenticated `GET /api/requests`
  - authenticated `GET /api/jobs`
  - authenticated `GET /api/reviews`
- unauthenticated `/api/runtime` returning 401

Completed `coordinator-jdv.3` on 2026-03-26.

Highlights:

- added generic operator request kinds for `review_detail`, `review_accept`, and `review_reject`
- extended the planner to parse review detail/accept/reject turns that reference a concrete review id
- extended the orchestrator to delegate those requests through the existing memory review tools while keeping the operator contract generic
- updated the repo docs to describe the converged review surface and its current memory-backed implementation boundary

Verification:

- `nix shell .#python -c python -m compileall src`
- `nix flake check`
- temp-state tool runs covering:
  - `planner.handle_turn` for `show review <id>`
  - `planner.handle_turn` for `accept review <id>`
  - `planner.handle_turn` for `reject review <id> because ...`

Follow-up issue:

- `coordinator-2xm`: remove unnecessary runtime assumptions from local review/dev flows

Completed `coordinator-2xm` on 2026-03-26.

Highlights:

- `run-tool` now auto-initializes the runtime directories and SQLite control-plane store
- review-only planner/orchestrator turns no longer require `INVOICE_AI_ERPNEXT_URL`
- orchestrator/planner delegate construction is now lazy instead of eagerly instantiating ERP-backed executors

Verification:

- `INVOICE_AI_STATE_DIR=$(mktemp -d)/state nix run . -- run-tool --request-file <review-only planner request>`
- confirmed review-only planner/orchestrator flow succeeds without `init-paths`
- confirmed review-only planner/orchestrator flow succeeds without `INVOICE_AI_ERPNEXT_URL`

Completed the first `coordinator-jdv.5` slice on 2026-03-26.

Highlights:

- added a disposable mock ERPNext backend under `src/invoice_ai/dev/mock_services.py`
- added a disposable mock Docling backend under `src/invoice_ai/dev/mock_services.py`
- added `dev-stack` for an interactive local operator stack
- added `dev-smoke-test` for a one-command mock-backed end-to-end verification path
- seeded the local dev stack with fake customer/item/supplier data and a sample supplier invoice document

Verification:

- `nix run . -- dev-smoke-test`
  - confirmed authenticated operator API startup
  - confirmed quote drafting through planner/orchestrator
  - confirmed quote-to-invoice conversion through planner/orchestrator
  - confirmed supplier document intake through extraction, ingest, and draft purchase-invoice creation
