# Implementation Plan 1

This document turns the first vertical slice into concrete code-facing units.

The target slice remains:

1. ingest supplier source material
2. normalize it into ERP-oriented draft state
3. ask for a quote in chat
4. create or revise a draft quotation
5. render a quote PDF preview

## First Code Units

### 1. Config And Runtime Wiring

Purpose:

- read environment and module-provided settings
- expose dependency endpoints and state paths to the app

Suggested files:

- `src/invoice_ai/config.py`
- `src/invoice_ai/paths.py`

### 2. ERP Connector

Purpose:

- implement the semantic tools from `docs/erp-tool-contract.md`
- use the payload shapes from `docs/erp-tool-schemas.md`

Suggested files:

- `src/invoice_ai/erp/client.py`
- `src/invoice_ai/erp/schemas.py`
- `src/invoice_ai/erp/tools.py`

This is the highest-priority implementation seam because almost every other unit depends on it.

### 3. Ingest Pipeline

Purpose:

- accept uploaded files, pasted text, or extracted text
- produce normalized supplier-invoice proposals

Suggested files:

- `src/invoice_ai/ingest/models.py`
- `src/invoice_ai/ingest/extract.py`
- `src/invoice_ai/ingest/normalize.py`

The first implementation does not need mailbox automation.

### 4. Approval Artifact Writer

Purpose:

- materialize approval requests into `/var/lib/invoice-ai/approvals`
- generate the `request.json`, `summary.md`, and `diff.json` artifacts defined in the contract

Suggested files:

- `src/invoice_ai/approvals/store.py`
- `src/invoice_ai/approvals/render.py`

### 5. Memory Store

Purpose:

- read and write markdown memory documents
- keep memory retrieval separate from ERP truth

Suggested files:

- `src/invoice_ai/memory/store.py`
- `src/invoice_ai/memory/render.py`

### 6. Quote Drafting Orchestrator

Purpose:

- gather ERP-linked context
- combine pricing, memory, and chat instructions
- produce quotation draft requests and revision updates

Suggested files:

- `src/invoice_ai/quotes/context.py`
- `src/invoice_ai/quotes/draft.py`
- `src/invoice_ai/quotes/revise.py`

### 7. PDF Artifact Renderer

Purpose:

- generate a deterministic quote PDF preview from the current draft

Suggested files:

- `src/invoice_ai/artifacts/pdf.py`
- `src/invoice_ai/artifacts/models.py`

## First Implementation Order

The recommended order is:

1. config and paths
2. ERP connector
3. approval artifact writer
4. ingest normalization models
5. quote drafting orchestrator
6. PDF artifact renderer

Reason:

- the connector and artifact writer are the hard boundaries
- once they exist, the ingest and drafting layers can call them without rethinking the architecture

## First Runnable Loop

The first runnable loop should be deliberately small:

1. read a supplier invoice file from disk
2. normalize it into a proposed purchase-invoice payload
3. either write a draft purchase invoice or emit an approval artifact
4. read a quote request from a structured input or CLI stub
5. create a draft quotation
6. render a quote PDF preview

No web UI is required for this first loop.

## Minimal Initial Package Layout

Suggested repo layout:

- `bin/invoice-ai`
- `src/invoice_ai/`
- `src/invoice_ai/config.py`
- `src/invoice_ai/erp/`
- `src/invoice_ai/ingest/`
- `src/invoice_ai/approvals/`
- `src/invoice_ai/memory/`
- `src/invoice_ai/quotes/`
- `src/invoice_ai/artifacts/`

## Immediate Coding Recommendation

After this planning step, the next coding task should be:

- implement the config layer and ERP connector skeleton first

That creates the narrowest usable seam for the rest of the application.
