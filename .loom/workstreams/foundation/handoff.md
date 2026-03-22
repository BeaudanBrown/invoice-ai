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
- added the first ERPNext entity map and draft revision model for quotes, invoices, projects, timesheets, purchase invoices, and pricing
- added the first semantic ERP tool contract covering allowed draft writes, approval-gated actions, and approval artifact requirements
- defined the persistent storage layout under `/var/lib/invoice-ai/` and aligned the NixOS module with the first subdirectory contract

Not completed:

- no application implementation exists yet
- no deployment has been wired into `nix-dotfiles` yet
- no concrete request/response payload schema has been written for the ERP tools yet
- no exact retention policy has been implemented in code yet

## Next Action

Use the foundation Beads epic to settle:

1. the exact request/response payload schema for the ERP tools
2. the first vertical slice from supplier invoice ingestion to quote drafting
3. the concrete NixOS module contract for NAS hosting
4. the first implementation slice after planning is complete

Current Beads child tasks:

- `coordinator-326.7`: persistent memory and review-artifact layout
- `coordinator-326.8`: first supplier-ingestion-to-quote vertical slice
