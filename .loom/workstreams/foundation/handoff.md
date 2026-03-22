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
- implemented the first application code scaffold under `src/invoice_ai/` for runtime configuration, dependency endpoint loading, and state-path resolution
- updated the flake package so `nix run . -- show-config` and `nix run . -- init-paths` exercise the runtime scaffold through the packaged CLI
- implemented the first ERP connector skeleton under `src/invoice_ai/erp/` with request/response envelopes, an ERPNext client, and semantic tool handlers for reads, pricing context, draft quotation creation/update, purchase-invoice drafting, and file attachment
- added `nix run . -- run-tool --request-file ...` as the first CLI seam for semantic ERP tool execution
- verified the connector against a disposable local mock ERP API for `erp.get_doc`, `erp.get_pricing_context`, `erp.create_draft_quotation`, and the approval-required purchase-invoice path

Not completed:

- no deployment has been wired into `nix-dotfiles` yet
- no exact retention policy has been implemented in code yet
- no real application code exists yet for intake normalization, approval artifact persistence, or quote PDF rendering
- the ERP connector still needs richer approval-artifact writing and broader ERP tool coverage

## Next Action

Use the foundation Beads epic to implement:

1. the approval artifact store and quote preview stub
2. richer ERP draft/revision flows on top of the semantic connector
3. the first runnable ERP-backed CLI loop
4. the first runnable service wiring into `nix-dotfiles`

Current Beads child tasks:

- `coordinator-326.14`: approval artifact store and quote preview stub
