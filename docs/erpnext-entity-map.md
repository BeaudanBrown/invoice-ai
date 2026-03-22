# ERPNext Entity Map

This document defines the first concrete `ERPNext` entity mapping for `invoice-ai`.

It is intentionally conservative:

- prefer native ERPNext doctypes and flows
- avoid shadow business models in the app layer
- keep the first vertical slice small enough to implement

## Design Rules

1. `ERPNext` is the source of truth for operational business data.
2. The agent should call native APIs and manipulate native doctypes wherever possible.
3. The app layer may keep review artifacts, markdown memory, and working revision snapshots, but it should not become a parallel ERP.
4. Draft-state edits are allowed. Submitted or destructive changes require approval according to the foundation policy.

## Core Mapping

### Customer

- Primary doctype: `Customer`
- Related doctypes: `Contact`, `Address`
- Purpose:
  - canonical client identity
  - billing and site contact details
  - customer-specific default terms and tax context

## Supplier

- Primary doctype: `Supplier`
- Related doctypes: `Contact`, `Address`
- Purpose:
  - canonical supplier identity
  - source for purchase invoices and subcontractor billing

## Items And Services

- Primary doctype: `Item`
- Related doctypes: `Item Group`, `UOM`
- Purpose:
  - labor line items
  - material and supply line items
  - travel/callout fees
  - subcontracted labor line items

Recommended first classification:

- service labor item
- material/supply item
- travel or misc charge item
- subcontracted labor item

The agent should prefer normal `Item` records for billable units rather than ad hoc free-text lines whenever a stable repeated concept exists.

## Pricing

- Primary doctypes: `Price List`, `Item Price`, `Pricing Rule`
- Purpose:
  - default buying and selling rates
  - customer-specific pricing exceptions
  - supplier-specific pricing behavior where ERPNext supports it

Recommended pricing stance:

- use `Item Price` and `Price List` as the default price memory backbone
- use `Pricing Rule` for explicit, repeatable pricing exceptions
- use markdown memory only for fluid instructions that do not belong as canonical structured pricing

## Quote Drafts

- Primary doctype: `Quotation`
- Purpose:
  - formal sales proposal
  - primary operator-facing draft quote object in ERPNext

Why:

- ERPNext treats a quotation as the estimated cost for a customer or lead
- quotation rates can be fetched from `Item Price`
- submitted quotations can create downstream sales documents

Recommended usage:

- the agent may create and revise draft `Quotation` records without approval
- submission of a quotation is approval-gated
- generated PDFs should be based on the quotation draft or submitted quotation, not on a parallel app-only object

## Job Container

- Primary doctype: `Project`
- Related doctype: `Task`
- Purpose:
  - job-level grouping for electrician-style work
  - linkage between customer, authorized work, timesheets, and supporting context

Why:

- ERPNext projects are task-driven and can be linked to a `Customer`
- projects can also be linked to a `Sales Order`
- tasks and timesheets can attach execution detail without turning the app layer into a project tracker

Recommended usage:

- create a `Project` once quoted work becomes authorized or otherwise needs execution tracking
- use `Task` only when task-level execution detail is actually useful
- do not require every quote to have a project before it becomes a draft

## Labor Tracking

- Primary doctype: `Timesheet`
- Related doctypes: `Project`, `Task`, `Sales Invoice`
- Purpose:
  - record billable employee hours
  - feed invoiceable time into downstream sales invoices

Why:

- ERPNext can fetch billable timesheets into a sales invoice
- timesheets naturally fit employee labor and project-linked work

Recommended usage:

- use `Timesheet` for internal labor hours
- prefer linking timesheets to `Project`, and optionally `Task`
- do not force subcontractor labor through timesheets if it is more naturally represented as supplier billing

## Sales Billing

- Primary doctype: `Sales Invoice`
- Related doctypes: `Quotation`, `Sales Order`, `Project`, `Timesheet`
- Purpose:
  - draft and final customer billing

Why:

- ERPNext can populate a sales invoice from quotation, sales order, delivery note, or project-linked timesheets
- project-linked timesheet billing is a native ERPNext path

Recommended usage:

- the agent may create and revise draft `Sales Invoice` records without approval
- submission is approval-gated
- for service-heavy work, combine project/timesheet-based labor with item-based materials and charges

## Supplier Invoice Ingestion

- Primary doctype: `Purchase Invoice`
- Related doctypes: `Supplier`, `Item`, `Project`
- Purpose:
  - capture supplier bills and equipment/material purchases
  - keep buying-side cost history current in ERPNext

Why:

- purchase invoices are the canonical place for supplier billing
- ERPNext supports supplier-specific invoice references and buying price behavior

Recommended usage:

- if supplier and item identities already exist and extraction confidence is high, the agent may create a draft `Purchase Invoice`
- if required master data is missing or confidence is low, the agent should create a review artifact and proposed mutations rather than silently inventing master data
- where useful, link costs to a `Project`

## Subcontracted Labor

- Primary doctypes: `Supplier`, `Purchase Invoice`, `Item`
- Optional related doctype: `Project`
- Purpose:
  - model hired external workers as suppliers rather than as internal employees

Recommended usage:

- treat subcontractors as `Supplier` records
- ingest their billed work through `Purchase Invoice`
- represent their billable cost using labor-related `Item` rows
- optionally link those costs to the relevant `Project`

## Optional Sales Execution Boundary

- Primary doctype: `Sales Order`
- Purpose:
  - record accepted commercial scope before project execution and invoicing

Recommended usage:

- keep `Sales Order` optional in v1
- use it when the operator wants a clearer boundary between accepted quote and executed work
- do not force the first vertical slice to depend on sales orders

## Recommended First-End-To-End Flow

1. ingest supplier bill source material
2. extract supplier, invoice reference, dates, totals, and line items
3. resolve existing `Supplier` and `Item` matches
4. create either:
   - a draft `Purchase Invoice`, or
   - a review artifact plus proposed ERP mutations if approval is required
5. answer a quote request in chat
6. retrieve `Customer`, prior `Quotation` and `Sales Invoice` history, and relevant pricing from `Item Price` and `Pricing Rule`
7. create or revise a draft `Quotation`
8. generate a PDF quote artifact from that draft

## Revision Model

The preferred revision model is hybrid:

- while a quote or invoice remains in `Draft`, the agent may revise the same ERPNext draft document in place
- the app layer should keep working revision snapshots and review artifacts outside ERPNext so conversational iteration does not flood the ERP with near-duplicate drafts
- once a quote or invoice crosses an approval boundary and is submitted, further changes should create a successor draft or use the ERP's explicit cancel/amend flow only with approval

This is the current recommendation because it keeps `ERPNext` authoritative while avoiding noisy history from every conversational tweak.

## First Vertical-Slice Data Shape

For the first implemented slice, the stable core records should be:

- `Customer`
- `Supplier`
- `Item`
- `Quotation`
- `Purchase Invoice`
- optionally `Project`

`Task`, `Timesheet`, and `Sales Order` should remain available but not mandatory for the first slice.

## Open Carry-Forward Items

These move into the next planning step:

- exact API/tool actions the agent may invoke directly
- exact approval artifact format
- exact on-disk revision snapshot layout under `/var/lib/invoice-ai/`
