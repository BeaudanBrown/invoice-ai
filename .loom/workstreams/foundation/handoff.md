# Handoff

## Status

Foundation setup started on 2026-03-21.

Completed:

- created a new local repo at `/home/beau/documents/projects/invoice-ai`
- initialized the repo on `main`
- symlinked it into the coordinator at `repos/invoice-ai`
- added the initial repo-local instruction guide
- added the first architecture and open-question docs
- added a foundation-stage `flake.nix`
- added a placeholder `services.invoice-ai` NixOS module for future NAS integration
- created coordinator Beads epic `coordinator-326` with the first architecture-decision child tasks
- ratified the foundation product boundary, approval policy, ERP-first rule, delegated-agent model, and first vertical slice in repo docs
- added explicit docs for the foundation spec, agent architecture, and memory model

Not completed:

- no application implementation exists yet
- no deployment has been wired into `nix-dotfiles` yet
- no concrete ERP entity mapping or API contract has been written yet
- no persistent memory layout under `/var/lib/invoice-ai/` has been finalized yet

## Next Action

Use the foundation Beads epic to settle:

1. the first ERP entity mapping and API contract
2. the first vertical slice from supplier invoice ingestion to quote drafting
3. the persistent memory and review-artifact layout under `/var/lib/invoice-ai/`
4. the concrete NixOS module contract for NAS hosting

Current Beads child tasks:

- `coordinator-326.5`: ERPNext entities and revision model
- `coordinator-326.6`: agent-to-ERP tool contract and approval gates
- `coordinator-326.7`: persistent memory and review-artifact layout
- `coordinator-326.8`: first supplier-ingestion-to-quote vertical slice
