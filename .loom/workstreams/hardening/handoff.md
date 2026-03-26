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

- service API is still missing enforced auth and fuller operator review surfaces
- request/job metadata exists now, but it is not yet exposed through a broader operator API
- operator review flows are incomplete
- extraction confidence and duplicate handling are still basic
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

1. SQLite-backed control-plane store
2. FastAPI operator service migration
3. sales-invoice and ERP-surface completion
4. review-action completion
5. ingest robustness
6. deployment and end-to-end verification

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
