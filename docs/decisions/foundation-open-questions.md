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

## Remaining Open Items

1. How should jobs and work orders be modeled in `ERPNext` for this project?
2. What exact ERPNext-native pricing constructs should the agent prefer first for labor and material pricing?
3. What should the persistent on-disk memory layout under `/var/lib/invoice-ai/` look like?
4. How should approval artifacts and structured diffs be represented on disk?
5. What is the exact first API contract between the main agent and the ERP mutation layer?
