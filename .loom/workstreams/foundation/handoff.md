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
- implemented the first filesystem-backed approval artifact writer under `src/invoice_ai/approvals/`
- implemented the first deterministic quote-preview PDF renderer under `src/invoice_ai/artifacts/`
- extended the CLI so `run-tool --write-approval-artifacts` materializes approval requests on disk and `render-quote-preview` writes a preview PDF into the configured artifacts tree
- implemented the first ingest normalization tool under `src/invoice_ai/ingest/` with source models, ERP-backed supplier/item resolution, proposal shaping, and filesystem-backed ingest record persistence
- extended the shared tool CLI so `ingest.normalize_supplier_invoice` can emit either a draft-ready ERP purchase-invoice request or an approval/review result
- implemented the first composed supplier-ingest flow so `ingest.create_purchase_invoice_draft` can normalize supplier input, create a draft `Purchase Invoice`, optionally attach the source file, and persist the composed ERP result alongside the ingest record
- implemented the first raw-document extraction layer under `src/invoice_ai/extract/` so `extract.supplier_invoice_from_document` can accept raw text or a local document path, use `Docling` for PDF text extraction when configured, emit a structured supplier-invoice candidate plus a ready-to-run ingest request, and surface low-confidence extraction through approval review
- implemented the first end-to-end supplier-document pipeline so `ingest.process_supplier_document` can start from a raw supplier document, run extraction, continue through normalization and draft `Purchase Invoice` creation when safe, and stop cleanly for review at either the extraction or ERP master-data stage
- implemented the first operator-facing orchestration facade under `src/invoice_ai/orchestrator/` so `orchestrator.handle_request` can accept a single request envelope, route supplier-document intake into `ingest.process_supplier_document`, route quote drafting into `quotes.create_draft`, and return a consistent stage/artifact/ERP-ref response shape
- extended the orchestration facade so quote revisions can route through `quotes.revise_draft`, quote follow-up turns can reuse `conversation_context.active_quote`, and the repo now has an explicit orchestrator contract doc for the transition from structured operator envelopes to chat-planned requests
- implemented the first planner layer under `src/invoice_ai/planner/` so free-form turns can be translated into structured orchestrator requests for supplier intake, quote drafting, and quote revision without bypassing the orchestrator or semantic tool layers
- implemented the first quote orchestration tool layer under `src/invoice_ai/quotes/` with customer/item resolution, ERP-backed quote context gathering, draft quotation creation, and draft quotation revision
- implemented the first filesystem-backed quotation revision store under `src/invoice_ai/revisions/` so working quote revisions persist outside ERPNext
- extended the shared tool CLI so `quotes.prepare_context`, `quotes.create_draft`, and `quotes.revise_draft` can drive ERP-backed quotation workflows and refreshed preview artifacts
- verified quote create, revise, and approval-required paths against a disposable local mock ERP API
- implemented the first HTTP control-plane service under `src/invoice_ai/service/` with `GET /healthz`, `GET /api/runtime`, and `POST /api/tools/run`
- extended the CLI with `serve-http` so the packaged app can run as a long-lived service instead of only ad hoc commands
- wired `modules/invoice-ai.nix` to provision a real `systemd.services.invoice-ai` unit with `ExecStartPre` path initialization and `ExecStart` for the HTTP service
- verified the service locally through `nix run . -- serve-http`, `curl` health/runtime probes, HTTP tool execution, `nix flake check`, and a NixOS module evaluation that confirmed the generated `ExecStart` and `ExecStartPre`

Not completed:

- no deployment has been wired into `nix-dotfiles` yet
- no exact retention policy has been implemented in code yet
- the ERP connector still needs broader semantic tool coverage and tighter ERPNext field mappings
- the current quote preview renderer is a deterministic stub, not a production template

## Next Action

Use the foundation Beads epic to implement:

1. the first composed ingest-to-ERP loop that chains ingest and ERP tools end to end
2. the first runnable service wiring into `nix-dotfiles`
3. tighter ERPNext field mappings and broader semantic tool coverage where the first vertical slice needs them
4. any cleanup or retention behavior needed around revisions, approvals, and generated artifacts

Current Beads child tasks:

- `coordinator-ymk`: extend the planner with memory-aware and model-assisted routing while keeping the same safe structured request boundary
