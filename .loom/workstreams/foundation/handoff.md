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
- added the first ERP tool payload schemas for the connector-facing semantic tool layer
- defined the persistent storage layout under `/var/lib/invoice-ai/` and aligned the NixOS module with the first subdirectory contract
- defined the concrete NixOS module service boundary, dependency inputs, runtime user/group, and host-owned versus repo-owned settings
- specified the first supplier-ingestion-to-quote vertical slice as an implementation-ready workflow
- added the first code-facing implementation plan and a real placeholder `invoice-ai` package entrypoint in the flake

Not completed:

- no application implementation exists yet
- no deployment has been wired into `nix-dotfiles` yet
- no exact retention policy has been implemented in code yet
- no real application code exists yet for the intake, ERP connector, approval artifact generation, or quote PDF path

## Next Action

Use the foundation Beads epic to settle:

1. the runtime config and path handling scaffold
2. the ERP connector skeleton for semantic tools
3. the approval artifact store and quote preview stub
4. the first runnable service wiring into `nix-dotfiles`

Current Beads child tasks:

- `coordinator-326.12`: runtime config and path handling scaffold
- `coordinator-326.13`: ERP connector skeleton for semantic tools
- `coordinator-326.14`: approval artifact store and quote preview stub
