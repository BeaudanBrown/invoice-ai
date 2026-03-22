# invoice-ai

Nix-native self-hosted AI invoicing workspace.

## Current Status

The repository currently exposes:

- a flake package with a minimal `invoice-ai` CLI
- a NixOS module under `modules/invoice-ai.nix`
- implementation specs for the first ERP-first vertical slice

## Runtime Scaffold

The current application scaffold can resolve runtime configuration and state
paths from environment variables that match the NixOS module contract.

Useful commands:

```bash
nix run . -- show-config
nix run . -- init-paths
nix run . -- run-tool --request-file request.json
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

## Current ERP Connector Surface

The current semantic ERP connector lives under `src/invoice_ai/erp/` and exposes:

- request/response envelopes for semantic ERP tools
- an `ERPNext` HTTP client using standard `/api/resource/*` and `/api/method/upload_file`
- a tool executor for:
  - `erp.get_doc`
  - `erp.list_docs`
  - `erp.get_linked_context`
  - `erp.get_pricing_context`
  - `erp.create_draft_quotation`
  - `erp.update_draft_quotation`
  - `erp.create_draft_purchase_invoice`
  - `erp.attach_file`

The CLI entrypoint for this layer is:

```bash
INVOICE_AI_ERPNEXT_URL=http://erpnext.local \
  nix run . -- run-tool --request-file request.json
```

`invoice-ai` is a self-hosted, open-source, Nix-native invoicing workspace for AI-assisted accounts receivable and accounts payable flows.

The target system should be able to:

- draft quotes and invoices from natural-language job descriptions
- draft client-ready invoices from natural-language job descriptions
- retrieve and reuse prior invoices, client context, tax settings, and service history
- ingest supplier invoices and receipts to maintain current cost and price intelligence
- run fully self-hosted on the NAS through `nix-dotfiles` as a NixOS module

## Current Status

This repository is currently in foundation mode. The core architecture decisions are now settled, and the next phase is to turn them into an implementation-ready vertical slice.

## Planned Stack

- ERP/data spine: `ERPNext`
- orchestration and agents: `n8n`
- local model serving: `Ollama`
- document ingestion and extraction: `Docling`
- deployment target: NixOS service module consumed from `nix-dotfiles`

## Immediate Goals

- define the ERP-first mutation and retrieval contracts
- define the delegated subagent instruction packs behind the single user-facing agent
- define the first vertical slice from supplier invoice ingestion through quote generation
- keep the NixOS module interface stable enough for later `nix-dotfiles` integration

## Key Docs

- `AGENTS.md`
- `docs/architecture.md`
- `docs/foundation-spec.md`
- `docs/erpnext-entity-map.md`
- `docs/erp-tool-contract.md`
- `docs/erp-tool-schemas.md`
- `docs/agent-architecture.md`
- `docs/memory.md`
- `docs/nixos-module-contract.md`
- `docs/storage-layout.md`
- `docs/vertical-slice-1.md`
- `docs/implementation-plan-1.md`
- `docs/decisions/foundation-open-questions.md`
- `.loom/workstreams/foundation/context.md`
- `.loom/workstreams/foundation/handoff.md`
