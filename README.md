# invoice-ai

Nix-native self-hosted AI invoicing workspace.

## Current Status

`invoice-ai` is no longer just a foundation repo. It now has a working control-plane scaffold with:

- a packaged CLI
- a FastAPI operator service
- an ERP-first semantic tool layer for `ERPNext`
- supplier-document extraction and ingest flows
- quote draft and revision flows
- sales invoice draft and revision flows
- quote-to-invoice draft conversion
- a planner and orchestrator for chat-facing routing
- markdown memory with review-gated suggestions
- filesystem-backed approvals, revisions, and PDF preview artifacts
- a local SQLite-backed control-plane metadata store for requests, jobs, reviews, artifacts, and idempotency indexes

The current user-facing surface is still API-first. A phone-first installable operator UI is designed but not yet implemented.

The repo is still incomplete as a product. The current stage is hardening and completion, not initial architecture discovery.

## Current Architecture

The implemented runtime shape is:

- `invoice-ai` control plane for planning, orchestration, review, and persistence
- `ERPNext` as the canonical operational system of record
- `Ollama` as an optional local planning/model-assist endpoint
- `Docling` as the current raw-document extraction dependency
- optional future integrations such as `n8n`, kept out of the core request path unless needed for external automation

The most important architectural rule remains:

- if `ERPNext` already provides the business capability, use the ERP API and document model instead of recreating it locally

## Runtime Commands

Useful commands:

```bash
nix run . -- show-config
nix run . -- init-paths
nix run . -- run-tool --request-file request.json
nix run . -- render-quote-preview --input-file quote.json
nix run . -- serve-http
```

Environment contract:

- `INVOICE_AI_LISTEN_ADDRESS`
- `INVOICE_AI_PORT`
- `INVOICE_AI_PUBLIC_URL`
- `INVOICE_AI_HOST_NAME`
- `INVOICE_AI_OPERATOR_TOKENS_FILE`
- `INVOICE_AI_STATE_DIR`
- `INVOICE_AI_CONTROL_PLANE_DB_PATH`
- `INVOICE_AI_DOCUMENTS_DIR`
- `INVOICE_AI_MEMORY_DIR`
- `INVOICE_AI_INGEST_DIR`
- `INVOICE_AI_APPROVALS_DIR`
- `INVOICE_AI_REVISIONS_DIR`
- `INVOICE_AI_ARTIFACTS_DIR`
- `INVOICE_AI_CACHE_DIR`
- `INVOICE_AI_ERPNEXT_URL`
- `INVOICE_AI_ERPNEXT_CREDENTIALS_FILE`
- `INVOICE_AI_OLLAMA_URL`
- `INVOICE_AI_DOCLING_URL`
- `INVOICE_AI_N8N_URL`

## Current System Surfaces

### ERP

The semantic ERP connector lives under `src/invoice_ai/erp/` and currently exposes:

- `erp.get_doc`
- `erp.list_docs`
- `erp.get_linked_context`
- `erp.get_pricing_context`
- `erp.create_draft_quotation`
- `erp.update_draft_quotation`
- `erp.create_draft_purchase_invoice`
- `erp.attach_file`

### Extraction

The extraction layer lives under `src/invoice_ai/extract/` and currently exposes:

- `extract.supplier_invoice_from_document`

It accepts raw text or a local document path, uses `Docling` for PDF extraction when configured, and emits structured supplier-invoice candidates for the ingest layer.

### Ingest

The ingest layer lives under `src/invoice_ai/ingest/` and currently exposes:

- `ingest.normalize_supplier_invoice`
- `ingest.create_purchase_invoice_draft`
- `ingest.process_supplier_document`
- `ingest.reprocess_record`

It can normalize supplier invoice input, stop for review when supplier/item matching is unresolved, and create draft `Purchase Invoice` records when the ERP path is safe.
It now also computes source fingerprints, flags extraction anomalies, checks for duplicate ingests before unsafe writes, and can reprocess stored ingest records from disk.

### Quotes

The quote layer lives under `src/invoice_ai/quotes/` and currently exposes:

- `quotes.prepare_context`
- `quotes.create_draft`
- `quotes.revise_draft`

It can gather ERP-backed quote context, create draft quotations, revise them, render preview PDFs, and persist local revision snapshots.

### Sales Invoices

The sales-invoice layer lives under `src/invoice_ai/invoices/` and currently exposes:

- `invoices.create_draft`
- `invoices.revise_draft`

It can create draft `Sales Invoice` records either from direct customer/item input or from an existing `Quotation`, revise draft sales invoices, render preview PDFs, and persist local revision snapshots.

### Orchestrator

The operator-facing orchestration layer lives under `src/invoice_ai/orchestrator/` and currently exposes:

- `orchestrator.handle_request`

It currently supports:

- `supplier_document_intake`
- `review_queue`
- `review_detail`
- `review_accept`
- `review_reject`
- `quote_draft`
- `quote_revision`
- `invoice_draft`
- `invoice_revision`

### Planner

The planner lives under `src/invoice_ai/planner/` and currently exposes:

- `planner.plan_turn`
- `planner.handle_turn`

It translates a narrow set of free-form operator turns into structured orchestrator requests and can optionally use `Ollama` for model-assisted routing. It now supports direct invoice drafting and quote-to-invoice turns in addition to the earlier quote and supplier-ingest paths.

### Memory

The memory layer lives under `src/invoice_ai/memory/` and currently exposes:

- `memory.list_documents`
- `memory.get_document`
- `memory.upsert_document`
- `memory.record_note`
- `memory.list_reviews`
- `memory.get_review`
- `memory.list_suggestions`
- `memory.get_suggestion`
- `memory.suggest_update`
- `memory.accept_suggestion`
- `memory.reject_suggestion`

## Current Weak Points

The current weak points are:

- thin ERP semantic coverage outside the first quote and purchase-invoice slice
- extraction quality is still narrower than it needs to be for repeated real use, even though anomalies, duplicate checks, and record reprocessing now exist
- operator auth is currently bearer-token-file based only; there is no richer role or policy model yet
- the current review-action path is still memory-backed; non-memory approval types have not yet been converged onto the same operator contract
- no real ERPNext-backed disposable integration stack yet; the current disposable path is mock-backed
- no actual `nix-dotfiles` deployment integration yet

## Current Service Surface

The current service entrypoint is:

```bash
nix run . -- serve-http
```

Current endpoints:

- `GET /healthz`
- `GET /api/runtime`
- `POST /api/tools/run`
- `GET /api/requests`
- `GET /api/requests/{request_id}`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/reviews`
- `GET /api/reviews/{review_id}`
- `GET /docs`
- `GET /openapi.json`

`POST /api/tools/run` accepts the same JSON envelope used by `run-tool`. It may also include `write_approval_artifacts: true` at the top level to persist approval artifacts while executing the request.

All `/api/*` endpoints now require `Authorization: Bearer <token>`, where the token is loaded from `INVOICE_AI_OPERATOR_TOKENS_FILE`. The service also emits `X-Request-ID` on every response and records the authenticated operator id into the control-plane store.

## Planned Operator UI

The intended user-facing product is a small phone-first installable PWA:

- chat-style layout
- voice-to-text as a first-class input path
- text input fallback
- current-session draft revision flow
- artifact preview and download

That UI does not exist yet. The current implemented user-facing surface is still:

- `POST /api/tools/run`
- `/docs`
- `/openapi.json`

The design for the upcoming UI lives in `docs/operator-ui.md`.

The operator token file is JSON and currently has this shape:

```json
{
  "operators": [
    {
      "operator_id": "local-dev",
      "token": "replace-this-token"
    }
  ]
}
```

## Fastest Local Test Loop

There is now a one-command disposable local dev stack for mock-backed end-to-end testing.

Fastest commands:

```bash
nix run . -- dev-stack
nix run . -- dev-smoke-test
```

`dev-stack` starts:

1. a disposable `invoice-ai` FastAPI service
2. a seeded mock ERPNext HTTP backend
3. a seeded mock Docling HTTP backend
4. a temp state tree plus local operator token file

It prints the service URL, bearer token, temp-state paths, and sample supplier document path, then stays up for manual interaction until `Ctrl-C`.

`dev-smoke-test` uses that same stack shape and verifies:

- authenticated operator API startup
- quote drafting through the planner/orchestrator path
- quote-to-invoice drafting through the planner/orchestrator path
- supplier document intake through extraction, ingest, and draft purchase-invoice creation

The current fake-data story is now:

- blank local state: yes
- fake operator auth: yes
- fake ERP backend: yes, built in
- fake Docling backend: yes, built in
- one-command disposable smoke path: yes
- real disposable ERPNext fixture: no, not yet

The remaining gap is not whether the control plane can be exercised locally. The remaining gap is proving the same loop against a more realistic ERPNext dependency and then carrying that integration cleanly into `nix-dotfiles`.

## Direction

The immediate project direction is:

1. harden the operator control plane
2. complete the remaining ERP and review business paths around the new sales-invoice surface
3. expand ERP semantic coverage and review flows
4. strengthen extraction, dedupe, and auditability
5. integrate cleanly into `nix-dotfiles` and add real end-to-end verification

## Key Docs

- `AGENTS.md`
- `docs/architecture.md`
- `docs/architecture-review-2026-03.md`
- `docs/completion-plan.md`
- `docs/control-plane-hardening.md`
- `docs/control-plane-store.md`
- `docs/dev-testing.md`
- `docs/schema-conventions.md`
- `docs/foundation-spec.md`
- `docs/erpnext-entity-map.md`
- `docs/erp-tool-contract.md`
- `docs/erp-tool-schemas.md`
- `docs/agent-architecture.md`
- `docs/memory.md`
- `docs/operator-ui.md`
- `docs/nixos-module-contract.md`
- `docs/storage-layout.md`
- `docs/orchestrator-contract.md`
- `docs/planner-contract.md`
- `docs/vertical-slice-1.md`
- `docs/implementation-plan-1.md`
