# Handoff

## Status

Hardening started on 2026-03-26 after the foundation lane completed its architecture-and-scaffold work.

Inherited completed work:

- packaged flake and NixOS module
- runtime config and persistent path scaffold
- HTTP service and CLI
- ERP semantic tools for the first quotation and purchase-invoice flows
- raw-document extraction, supplier ingest, and composed supplier-document processing
- quote draft and revision orchestration with preview PDFs and local revisions
- planner and orchestrator layers
- markdown memory with review-gated suggestions
- approval artifact persistence and review indexing

## Current Risks

- service API is still a thin tool runner without auth or request identity
- no first-class job/event ledger exists yet
- sales invoices are still missing from the ERP semantic and operator layers
- operator review flows are incomplete
- extraction confidence and duplicate handling are still basic
- deployment and verification are still mostly mock-driven

## Current Next Action

Use the hardening Beads epic to drive:

1. operator-service hardening
2. sales-invoice and ERP-surface completion
3. review-action completion
4. ingest robustness
5. deployment and end-to-end verification

## Notes

- foundation context remains useful for historical decisions, but active work should anchor on the hardening docs and Beads epic
- the current architectural review is in `docs/architecture-review-2026-03.md`
- the current completion roadmap is in `docs/completion-plan.md`
- the concrete service/store/schema decisions are in `docs/control-plane-hardening.md`
