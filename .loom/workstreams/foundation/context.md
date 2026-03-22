# Foundation

## Objective

Stand up the `invoice-ai` project as a tracked, Nix-native repository and solidify the first architecture and workflow decisions needed to begin implementation.

## Current Direction

- self-hosted only
- open-source core stack
- `ERPNext` + `n8n` + `Ollama` + `Docling`
- hosted on the NAS through `nix-dotfiles`
- exported as a NixOS module from this repo
- one user-facing agent with delegated instruction-driven subagents
- ERP-first behavior through native APIs and document models
- markdown memory only for fluid natural-language guidance, not structured ERP facts

## Primary Docs

- `AGENTS.md`
- `README.md`
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

## Beads

- Epic: `coordinator-326`
- `coordinator-326.13`: implement ERP connector skeleton for semantic tools
- `coordinator-326.14`: implement approval artifact store and quote preview stub

## Current Implementation State

- `src/invoice_ai/config.py` resolves service settings, dependency endpoints, and path settings from environment variables
- `src/invoice_ai/paths.py` defines the persistent runtime path model and can create the required directory tree
- `src/invoice_ai/cli.py` currently exposes `show-config` and `init-paths`
- `src/invoice_ai/erp/client.py` implements the first ERPNext transport layer over standard REST endpoints
- `src/invoice_ai/erp/schemas.py` defines the semantic tool envelopes and approval payload model
- `src/invoice_ai/erp/tools.py` dispatches the first semantic ERP tool set
- `src/invoice_ai/cli.py` now also exposes `run-tool` for JSON tool execution
- `nix run . -- show-config` and `nix run . -- init-paths` are the current smoke tests
- `nix run . -- run-tool --request-file ...` is the current semantic ERP connector test seam
