# Foundation Spec

## Product Boundary

`invoice-ai` is a chat-first AI control layer over `ERPNext`.

It should:

- ingest files, text, and links into ERP-oriented workflows
- create and revise quotes and invoices
- answer questions against ERP-backed history
- generate operator-facing artifacts, especially PDF quotes and invoices
- keep the ERP state current through API-driven interactions

It should not:

- send documents to customers or suppliers in v1
- replace ERPNext's existing business logic with ad hoc app-local reimplementation
- rely on raw documents as the primary retrieval source once data has been ingested into the ERP

## Canonical System Of Record

`ERPNext` is the canonical source for:

- customers
- suppliers
- items and services
- quotations
- sales invoices
- purchase invoices
- taxes and accounting-related business records
- persistent price history

The custom layer in this repo owns:

- chat orchestration
- delegated subagent instruction packs
- ingestion routing
- extraction and normalization helpers
- review artifacts and diffs
- markdown-based natural-language memory

The first concrete ERP mapping for these responsibilities lives in `docs/erpnext-entity-map.md`.

The first semantic agent-to-ERP interface lives in `docs/erp-tool-contract.md`.

The first concrete payload schemas for that interface live in `docs/erp-tool-schemas.md`.

## Primary Interaction Model

There is one user-facing agent.

That agent is responsible for delegating work to specialized subagents or toolpacks for:

- intake and classification
- ERP mutation planning and execution
- quote drafting
- invoice drafting
- memory curation
- review and explanation

These subagents are implementation details. The user should experience one coherent interface.

## Approval Policy

### Allowed Without Approval

- create draft quotes
- create draft invoices
- revise draft quotes and invoices
- ingest documents into staging flows
- attach supporting documents and notes
- answer questions and generate review artifacts
- update markdown memory records
- update existing non-destructive draft-state ERP records

### Approval Required

- creating new master data such as customers, suppliers, items, service codes, and pricing rules
- submitting or finalizing quotes and invoices
- deleting records
- cancelling submitted documents
- bulk merges or bulk rewrites
- changing accounting, tax, or other critical ERP configuration

## Pricing Policy

The agent should prefer:

1. current user instruction
2. stored natural-language instructions or operator preferences
3. historical consistency from ERP data

Pricing should mainly be used to keep ERPNext current and internally coherent.

For v1, the default retrieval emphasis is:

- latest relevant supplier cost data
- latest relevant labor pricing data
- client-specific historical pricing where present

The exact numeric pricing behavior should use native ERPNext constructs where possible rather than app-local shadow logic.

## Quotes Versus Invoices

Quotes and invoices are distinct ERP document types.

- quotes are proposals with revision flow
- invoices are payment claims against authorized or completed work

The agent should support conversational refinement for both, but revisions should produce explicit new draft revisions rather than silent destructive overwrites. Superseded revisions should usually be hidden from the primary operator view, not deleted.

## First Supported Business Shape

The first intended business shape is an electrician:

- labor hours
- materials and supplies
- subcontracted labor from other workers

The internal design should remain generic so the same flow works for other field-service businesses.

## First Vertical Slice

The first implementation slice should cover:

1. ingest a supplier invoice PDF or pasted text
2. extract and normalize supplier cost data
3. write the proposed result into ERP-oriented staging or draft records
4. answer a quote request in chat using ERP-backed pricing and history
5. generate a draft quote PDF plus structured intermediates

## ERP-First Rule

If `ERPNext` already provides a business capability, the agent should use the ERP API or native document model rather than trying to recreate that capability manually in the app layer.
