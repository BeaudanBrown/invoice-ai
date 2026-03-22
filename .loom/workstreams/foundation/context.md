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
- `docs/agent-architecture.md`
- `docs/memory.md`
- `docs/decisions/foundation-open-questions.md`

## Beads

- Epic: `coordinator-326`
- `coordinator-326.5`: map ERPNext entities and the revision model
- `coordinator-326.6`: define the agent-to-ERP tool contract and approval gates
- `coordinator-326.7`: define the persistent memory and review-artifact layout
- `coordinator-326.8`: specify the first supplier-ingestion-to-quote vertical slice
