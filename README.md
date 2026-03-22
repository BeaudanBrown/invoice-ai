# invoice-ai

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
- `docs/storage-layout.md`
- `docs/vertical-slice-1.md`
- `docs/decisions/foundation-open-questions.md`
- `.loom/workstreams/foundation/context.md`
- `.loom/workstreams/foundation/handoff.md`
