# Foundation Decisions And Remaining Open Items

## Ratified Decisions

### Product Boundary

- v1 is a chat-first control layer that drafts quotes and invoices, answers questions, ingests source material, and generates operator-facing artifacts
- v1 does not send documents automatically
- PDF is the primary artifact, with structured intermediate forms allowed

### ERP Boundary

- `ERPNext` is the canonical source for customers, suppliers, items, services, quotations, invoices, purchase history, and pricing history
- the agent should primarily interact with `ERPNext` through native APIs and document models
- the app layer should not manually recreate capabilities that `ERPNext` already provides internally

### Agent Model

- there is one user-facing agent
- that agent delegates to narrower subagents/instruction packs for intake, ERP mutation, drafting, memory, and review
- a large part of the repo will be markdown scaffolding and skills for those delegated agents

### Approval Policy

- non-destructive draft-state work on existing records is allowed
- creating new master data requires approval
- destructive actions require approval
- final submission or cancellation of business documents requires approval

### Retrieval And Memory

- retrieval should prefer structured ERP data
- documents are primarily for ingestion
- markdown memory is for fluid natural-language guidance, not structured accounting truth
- job-level memory is in scope

### Pricing Priorities

- current user instruction is highest priority
- stored instructions and relationship memory come next
- historical ERP consistency follows after that
- latest relevant supplier and labor pricing should be used to keep the ERP current

### Deployment

- the repo exports a single NixOS module
- `nix-dotfiles` should be able to import the flake directly
- persistent mutable app storage should live under `/var/lib/invoice-ai/`

### Orchestration

- the repo-local `invoice-ai` control plane is now the canonical planner/orchestrator for the operator request path
- `n8n` is optional integration infrastructure for later automation and should not be required for the core chat-to-ERP loop

## Remaining Open Items

1. What exact job and work-order model in `ERPNext` should anchor quote and invoice drafting for field-service work?
2. What exact ERPNext-native pricing constructs should the agent prefer first for labor, travel, subcontractor recovery, and materials?
3. What should the hardening-stage auth, idempotency, and audit model be for the operator API?
4. What retention and compaction policy should apply to revisions, approvals, ingest records, jobs, and events?
5. What is the exact end-to-end deployment and verification path through `nix-dotfiles` on the NAS host?
