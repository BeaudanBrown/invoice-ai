# invoice-ai

Nix-native self-hosted AI invoicing workspace.

## Current Status

`invoice-ai` is no longer just a foundation repo. It now has a working control-plane scaffold with:

- a packaged CLI
- a small HTTP service
- an ERP-first semantic tool layer for `ERPNext`
- supplier-document extraction and ingest flows
- quote draft and revision flows
- a planner and orchestrator for chat-facing routing
- markdown memory with review-gated suggestions
- filesystem-backed approvals, revisions, and PDF preview artifacts

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
- `INVOICE_AI_STATE_DIR`
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

It can normalize supplier invoice input, stop for review when supplier/item matching is unresolved, and create draft `Purchase Invoice` records when the ERP path is safe.

### Quotes

The quote layer lives under `src/invoice_ai/quotes/` and currently exposes:

- `quotes.prepare_context`
- `quotes.create_draft`
- `quotes.revise_draft`

It can gather ERP-backed quote context, create draft quotations, revise them, render preview PDFs, and persist local revision snapshots.

### Orchestrator

The operator-facing orchestration layer lives under `src/invoice_ai/orchestrator/` and currently exposes:

- `orchestrator.handle_request`

It currently supports:

- `supplier_document_intake`
- `review_queue`
- `quote_draft`
- `quote_revision`

### Planner

The planner lives under `src/invoice_ai/planner/` and currently exposes:

- `planner.plan_turn`
- `planner.handle_turn`

It translates a narrow set of free-form operator turns into structured orchestrator requests and can optionally use `Ollama` for model-assisted routing.

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

- no sales-invoice drafting path yet
- thin ERP semantic coverage outside the first quote and purchase-invoice slice
- extraction quality is still narrow and confidence handling is basic
- the HTTP service is still a thin tool runner rather than a hardened operator API
- no first-class workflow/job ledger yet
- no end-to-end approval actions through the operator surface yet
- no disposable integration stack or broad end-to-end test suite yet
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

`POST /api/tools/run` accepts the same JSON envelope used by `run-tool`. It may also include `write_approval_artifacts: true` at the top level to persist approval artifacts while executing the request.

## Direction

The immediate project direction is:

1. harden the operator control plane
2. complete the first missing business paths, especially sales invoices
3. expand ERP semantic coverage and review flows
4. strengthen extraction, dedupe, and auditability
5. integrate cleanly into `nix-dotfiles` and add real end-to-end verification

## Key Docs

- `AGENTS.md`
- `docs/architecture.md`
- `docs/architecture-review-2026-03.md`
- `docs/completion-plan.md`
- `docs/control-plane-hardening.md`
- `docs/schema-conventions.md`
- `docs/foundation-spec.md`
- `docs/erpnext-entity-map.md`
- `docs/erp-tool-contract.md`
- `docs/erp-tool-schemas.md`
- `docs/agent-architecture.md`
- `docs/memory.md`
- `docs/nixos-module-contract.md`
- `docs/storage-layout.md`
- `docs/orchestrator-contract.md`
- `docs/planner-contract.md`
- `docs/vertical-slice-1.md`
- `docs/implementation-plan-1.md`
