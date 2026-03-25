# Hardening

## Objective

Take the existing `invoice-ai` scaffold and turn it into a hardened, completion-oriented operator system.

## Current Direction

- keep the project self-hosted and Nix-native
- keep `ERPNext` as the canonical system of record
- treat the repo-local `invoice-ai` control plane as the canonical planner/orchestrator for the operator path
- treat `Ollama` and `Docling` as supporting dependencies
- treat `n8n` as optional integration infrastructure rather than a core runtime dependency
- preserve approval-gated actions for master-data creation, destructive operations, and final submission

## Priority Gaps

1. the service surface needs auth, auditability, idempotency, and job tracking
2. the outbound sales-invoice path is still missing
3. ERP semantic tool coverage is still too narrow
4. the review surface is incomplete beyond list and partial inspect flows
5. extraction and ingest need better confidence, dedupe, and reprocessing behavior
6. the repo still needs a real `nix-dotfiles` integration and end-to-end verification path

## Primary Docs

- `AGENTS.md`
- `README.md`
- `docs/architecture.md`
- `docs/architecture-review-2026-03.md`
- `docs/completion-plan.md`
- `docs/foundation-spec.md`
- `docs/erpnext-entity-map.md`
- `docs/erp-tool-contract.md`
- `docs/erp-tool-schemas.md`
- `docs/memory.md`
- `docs/nixos-module-contract.md`
- `docs/storage-layout.md`
- `docs/orchestrator-contract.md`
- `docs/planner-contract.md`

## Working Rule

Prefer finishing and hardening the existing stack over adding new clever planning behavior.
