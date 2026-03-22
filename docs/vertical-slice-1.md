# Vertical Slice 1

## Goal

Implement one narrow end-to-end workflow that proves the core value of `invoice-ai` without reopening the larger architecture.

The first slice is:

1. ingest a supplier invoice
2. normalize it into ERP-oriented draft state
3. ask for a quote in chat
4. draft a quote PDF using ERP-backed history and pricing context

## Why This Slice

This slice exercises the key system promises:

- document ingestion
- ERP-first state updates
- pricing retrieval
- chat-driven drafting
- operator-facing PDF output

It also stays narrow enough to avoid premature expansion into full job management, final invoicing, payments, or mail automation.

## Inputs

### Supplier Ingestion Input

At least one of:

- uploaded supplier invoice PDF
- pasted invoice text
- uploaded image/scan with readable invoice data

### Quote Drafting Input

A chat instruction like:

> quote Acme for emergency switchboard repair, 3 hours onsite, one replacement switch, and travel

Minimum required context:

- resolvable customer
- enough line-item intent to draft a plausible quote

## Preconditions

The slice assumes:

- `ERPNext` is reachable through the connector
- at least one existing `Customer` already exists
- at least one existing `Supplier` already exists
- at least some relevant `Item` records already exist for labor and material concepts

Master-data creation remains approval-gated, so the slice must handle missing masters by producing proposals rather than silently inventing them.

## Step 1: Ingest Supplier Source

The main agent routes the source material to the intake and ERP subagents.

Expected extracted fields:

- supplier identity
- supplier invoice reference
- invoice date
- totals
- line items

Expected outputs:

- normalized extraction payload
- matched or unresolved supplier
- matched or unresolved items

## Step 2: Resolve ERP Matches

The ERP subagent attempts to map extracted entities onto existing ERP records.

Expected lookups:

- `Supplier`
- `Item`
- relevant price context if needed for reconciliation

Branching behavior:

- if all required masters are confidently resolved, continue to draft `Purchase Invoice`
- if not, produce approval-gated proposals for missing suppliers, items, or pricing structures

## Step 3: Create Draft Purchase State

If the prerequisites are satisfied, the agent creates a draft `Purchase Invoice`.

Expected outputs:

- ERP draft purchase invoice reference
- attached source material
- stored ingest artifact under `/var/lib/invoice-ai/ingest`

If direct ERP write is not allowed yet because of unresolved masters, the output becomes:

- review proposal
- structured mutation request
- no unsafe ERP write

## Step 4: Retrieve Quote Context

The user asks for a quote in chat.

The system retrieves:

- `Customer`
- prior `Quotation` history
- prior `Sales Invoice` history
- current relevant `Item Price` and `Pricing Rule` context
- optional recent `Purchase Invoice` cost context
- markdown memory for operator, client, or job-specific guidance

## Step 5: Draft Quote

The drafting agent assembles a draft `Quotation`.

The quote should support:

- labor line items
- material line items
- optional travel/callout charges
- optional subcontractor-related recovery lines where appropriate

Expected outputs:

- draft `Quotation` in ERPNext
- structured quote representation
- generated PDF preview

## Step 6: Conversational Revision

The operator can refine the quote in chat.

Examples:

- increase labor from 3 to 4 hours
- reduce materials margin
- make the description clearer
- itemize travel separately

Expected behavior:

- update the same draft quotation while it remains draft
- keep working revision snapshots under `/var/lib/invoice-ai/revisions`
- regenerate the PDF preview

## Approval Boundaries

Within this slice:

- draft `Purchase Invoice` creation is allowed only when supplier and item masters already exist and confidence is high
- draft `Quotation` creation and revision are allowed
- new master data creation requires approval
- quotation submission requires approval
- purchase invoice submission requires approval

## Outputs

The slice is successful when it produces:

- one normalized ingest record
- one draft purchase path or a structured approval proposal
- one draft quotation in ERPNext
- one quote PDF preview
- linked review artifacts where approval was needed

## Explicit Non-Goals

This slice does not require:

- sending quotes or invoices
- submitted or finalized customer billing
- automated email ingestion
- automated payment reconciliation
- a full operator dashboard
- a complete project/task/timesheet workflow

## Implementation Notes

The minimum implementation surface should be:

1. intake parsing
2. ERP lookup and draft mutation tools
3. approval artifact generation
4. quote PDF generation
5. local revision and ingest artifact persistence

Everything else should be deferred until this loop works.
