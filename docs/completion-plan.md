# Completion Plan

This plan replaces the old "first implementation slice" framing with a completion-oriented roadmap for the existing stack.

## Goal

Take the current scaffolded control plane and turn it into a credible first operator-facing product for:

- supplier document intake
- quote drafting and revision
- sales invoice drafting and revision
- review-gated memory and approval actions
- NAS-hosted Nix-native deployment

## Stage 1: Control Plane Hardening

Objective:

- turn the current HTTP tool runner into a real operator service

Required outcomes:

- `FastAPI`-based operator API
- authenticated operator API
- request and job identifiers
- local SQLite-backed control-plane store
- persistent audit/event log
- idempotency keys for ERP write actions
- review queue inspection and action endpoints through the main operator surface
- stricter typed request, response, and store schemas

Current progress:

- the schema hardening pass is complete, with `Pydantic` boundary models documented in `docs/schema-conventions.md`
- the SQLite-backed metadata store is now in place for requests, jobs, events, reviews, artifacts, ingest indexes, memory suggestion indexes, and ERP-write idempotency fingerprints
- the FastAPI/ASGI service migration is now in place over the store-backed runtime
- bearer-token operator auth is now enforced on the `/api/*` surface from a host-provided token file
- the operator API now exposes authenticated request, job, event, and review inspection endpoints over the control-plane store

Acceptance:

- the operator surface can inspect review items and execution history without dropping to raw tool calls
- write actions are traceable and replay-safe
- long-running operations have stable job state instead of only synchronous responses
- the service boundary no longer depends on the stdlib HTTP server

## Stage 2: ERP Surface Completion

Objective:

- make the ERP semantic layer cover the first real business loop end to end

Required outcomes:

- draft sales invoice creation and revision
- quote-to-invoice conversion path
- master-data proposal flows for missing customers, suppliers, and items
- richer item, price, tax, and linked-context support
- explicit approval-gated lifecycle actions for submit/cancel/delete

Acceptance:

- the agent can create and revise both quotations and sales invoices safely through semantic ERP tools
- missing master data is proposed consistently instead of improvised ad hoc

Current progress:

- semantic ERP tools now cover draft quotation create/revise, draft sales-invoice create/revise, and draft purchase-invoice creation
- quote-to-invoice drafting is now explicit through the invoice tool layer and planner/orchestrator surface
- remaining work in this stage is broader ERP semantics and master-data proposal depth rather than the first sales-invoice vertical slice itself

## Stage 3: Ingest Hardening

Objective:

- make supplier-document intake robust enough for repeated real use

Required outcomes:

- better PDF and image extraction behavior
- duplicate detection for supplier invoices and source files
- stronger line-item normalization and matching
- clearer extraction confidence and anomaly reporting
- reprocessing path for rejected or partial ingests

Acceptance:

- the system can reliably stop unsafe ingests for review
- ingest records clearly show extraction, normalization, ERP write, and attachment outcomes

Current progress:

- extraction results now include anomaly reporting alongside confidence and warnings
- source-fingerprint duplicate checks now stop repeated ingests before unsafe ERP writes
- ingest records can now be replayed through `ingest.reprocess_record`
- remaining work in this stage is stronger matching/extraction quality and a broader duplicate strategy, not the absence of a duplicate/reprocess path

## Stage 4: Review And Memory Completion

Objective:

- make approvals and memory review consistent across the operator surface

Required outcomes:

- inspect specific review items by id
- accept and reject review items through the same operator-facing path
- unify memory review and other approval shapes where possible
- keep markdown memory scoped to soft guidance rather than ERP truth

Acceptance:

- the operator can review and resolve memory and other gated actions from chat or a structured review client using one common contract

Current progress:

- the operator surface now supports review queue listing, review detail inspection, and accept/reject actions through the planner/orchestrator path
- the current converged implementation is still memory-backed; broader approval types still need to adopt the same review contract

## Stage 5: Deployment And Verification

Objective:

- prove the stack on the actual Nix/NAS path and add realistic verification

Required outcomes:

- `nix-dotfiles` integration contract exercised for the NixOS module
- the `invoice-ai` module can deploy ERPNext through OCI containers as part of the same product boundary
- retention and cleanup policy implemented for approvals, revisions, artifacts, cache, and ingest state
- retention and backup policy documented for ERPNext site and database state
- disposable end-to-end verification path against the embedded ERPNext dependency stack
- documented recovery and troubleshooting path

Acceptance:

- the repo can be imported cleanly as a NixOS module in `nix-dotfiles`
- the module can stand up both the AI control plane and embedded ERPNext on the NAS path
- the combined service can be verified end to end against the same deployment shape it intends to run in production

Current progress:

- a disposable mock-backed dev stack now exists through `nix run . -- dev-stack`
- a one-command mock-backed smoke path now exists through `nix run . -- dev-smoke-test`
- the local CLI/operator dev path no longer requires pre-running `init-paths` or setting `INVOICE_AI_ERPNEXT_URL` for review-only flows
- the first `nix-dotfiles` import and targeted subsystem evaluation path now exist for the AI control plane itself
- the module now supports `erpnext.mode = "embedded"` through OCI containers plus bootstrap jobs for bench configuration, default-site creation, and stable site config
- remaining work in this stage is retention/backup policy, service-user/API credential bootstrap, and proving the same flows against that embedded stack instead of mocks

## Stage 6: Operator UI

Objective:

- turn the operator API into the phone-first installable product surface

Required outcomes:

- installable PWA shell
- text input plus speech-to-text input
- session-scoped chat-style interaction
- deterministic summary/result rendering over planner/orchestrator responses
- artifact preview/download HTTP support
- review cards and actions through the UI

Acceptance:

- a user can open the app on a phone, speak a request, and receive a quote or invoice artifact
- the same user can revise the current draft through follow-up voice or text turns
- the UI does not require direct ERP usage for the main loop

Current progress:

- the backend operator API exists
- the planner/orchestrator path already supports quote, invoice, supplier-intake, and review flows
- the first UI-facing API seam now exists through `POST /api/ui/turn`
- authenticated artifact preview/download now exists through `GET /api/artifacts/file/{relative_path}`
- a first installable PWA shell now exists, served by the FastAPI service with session-scoped chat history, token-based setup, and artifact/review cards
- remaining work in this stage is voice-flow refinement, phone polish, and the gap between the minimal shell and a production-ready operator experience

## Prioritization

The recommended order is:

1. control plane hardening
2. sales-invoice and ERP surface completion
3. review-action completion
4. ingest hardening
5. deployment and verification around the combined invoice-ai plus ERPNext module
6. operator UI

Reason:

- the current architectural risk is not planning quality
- it is unsafe or incomplete execution around otherwise-good boundaries

## Deliberate Deferrals

These are not on the critical path for the next completion phase:

- outbound email sending
- automated mailbox ingestion
- packaging and operating every dependency inside this repo
- a full custom web dashboard replacing ERPNext

## Exit Criteria

This phase is complete when:

1. a user can ingest supplier documents, draft quotes, and draft invoices through the operator surface
2. review-gated actions are inspectable and actionable without raw tool knowledge
3. the runtime has auth, auditability, idempotent write handling, and stable job records
4. the NixOS module is exercised through `nix-dotfiles` as one combined product deployment
5. real end-to-end verification exists beyond mocks against the embedded ERPNext stack
6. a user-facing installable operator UI exists for the main quote/invoice loop
