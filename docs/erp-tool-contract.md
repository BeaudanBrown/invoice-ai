# ERP Tool Contract

This document defines the first tool contract between the main `invoice-ai` agent, its delegated ERP subagent, and `ERPNext`.

The goal is not to give the main agent arbitrary raw API power. The goal is to expose a narrow, explicit, auditable tool surface that still preserves nearly full ERPNext capability.

## Contract Principles

1. The main agent should use semantic tools, not hand-rolled HTTP calls.
2. The ERP subagent may translate those semantic tools into `ERPNext` REST API calls and approved whitelisted method calls.
3. State-changing actions must respect the approval policy from the foundation spec.
4. If `ERPNext` already has native document flow for an operation, the tool contract should follow that flow rather than introducing app-local replacements.
5. The contract should be version-tolerant where possible and prefer standard Frappe REST endpoints.

## Authentication And Transport

The connector should use token-based API authentication by default.

Preferred transport shape:

- base document CRUD: `/api/resource/{doctype}` and `/api/resource/{doctype}/{name}`
- whitelisted method calls: `/api/method/{dotted.path}`
- file upload: `/api/method/upload_file`

For compatibility, the first implementation should target the standard `/api/` endpoints. If the target instance is confirmed to be Frappe v15+, the connector may later adopt `/api/v2/` selectively.

## Document State Model

The connector must treat document status as a first-class control boundary:

- `docstatus = 0`: Draft
- `docstatus = 1`: Submitted
- `docstatus = 2`: Cancelled

The main rule is:

- draft documents may be created and revised by allowed tools
- submitted documents may not be silently mutated
- cancelled or delete-like flows are always approval-gated

## Read Tools

These tools are safe by default and require no approval.

### `erp.get_doc`

Purpose:

- fetch a document by doctype and name

Typical usage:

- retrieve a `Customer`, `Quotation`, `Sales Invoice`, `Purchase Invoice`, `Project`, `Supplier`, or `Item`

### `erp.list_docs`

Purpose:

- query a doctype with filters, ordering, field selection, and pagination

Typical usage:

- search recent quotations for a customer
- find purchase invoices for a supplier
- find items with matching names or codes

### `erp.get_linked_context`

Purpose:

- fetch the minimum linked context needed for reasoning

Examples:

- customer plus recent quotations and invoices
- supplier plus recent purchase invoices
- item plus recent pricing and usage
- project plus tasks, timesheets, and related commercial docs

This may be implemented as multiple underlying ERP requests, but it should be exposed to the main agent as one semantic tool.

### `erp.get_pricing_context`

Purpose:

- retrieve the current usable pricing context for one or more items or service concepts

Expected sources:

- `Item Price`
- `Price List`
- `Pricing Rule`
- recent `Purchase Invoice` and `Sales Invoice` history

## Allowed Write Tools Without Approval

These actions are allowed because they are either draft-state, non-destructive, or app-owned.

### `erp.create_draft_quotation`

Creates a draft `Quotation` using existing master data.

### `erp.update_draft_quotation`

Updates an existing draft `Quotation`.

Guardrails:

- only allowed while the document remains draft
- should not silently submit

### `erp.create_draft_sales_invoice`

Creates a draft `Sales Invoice` using existing master data and linked context.

### `erp.update_draft_sales_invoice`

Updates an existing draft `Sales Invoice`.

### `erp.create_draft_purchase_invoice`

Creates a draft `Purchase Invoice` only when:

- supplier identity is already resolved to an existing `Supplier`
- required item/service mapping is resolved enough to avoid creating master data implicitly

If either condition fails, the tool must refuse direct write and instead return a review proposal.

### `erp.update_draft_purchase_invoice`

Updates an existing draft `Purchase Invoice`.

### `erp.attach_file`

Uploads and attaches a file to an ERP document using the native upload endpoint.

Examples:

- original supplier PDF
- generated comparison sheet
- generated quote PDF

### `erp.add_comment_or_note`

Adds non-destructive comments, remarks, or linked explanatory text where appropriate.

This should be used sparingly and should not become a substitute for structured fields.

## Approval-Gated Tools

These actions must produce an approval artifact before execution.

### Master Data Creation

- `erp.create_customer`
- `erp.create_supplier`
- `erp.create_item`
- `erp.create_or_update_pricing_rule`
- creation of other new canonical masters such as addresses, contacts, or tax-linked defaults when those are not purely derived side effects of an already-approved master-data action

### Submission And Finalization

- `erp.submit_quotation`
- `erp.submit_sales_invoice`
- `erp.submit_purchase_invoice`
- any equivalent action that changes a submittable document from draft to submitted

### Destructive Or Risky Mutations

- `erp.cancel_doc`
- `erp.delete_doc`
- `erp.amend_doc`
- bulk merge or bulk rewrite operations
- accounting or tax configuration changes
- naming-series or permission changes

### Unsafe Escape Hatches

- arbitrary `/api/method/...` invocation not on the allowlist
- arbitrary raw delete/update operations outside the semantic tool layer

## Approval Artifact Requirements

Every approval-gated tool invocation must be paired with a structured review artifact containing:

- requested action
- target doctype and document if already known
- why the action is needed
- fields that will be created or changed
- confidence and ambiguity notes
- linked source material and generated diffs where relevant

For example:

- proposed new `Supplier`
- proposed new `Item`
- proposed submission of `Quotation QTN-0001`
- proposed cancellation of `Sales Invoice ACC-SINV-0009`

## Main-Agent View Versus ERP-Subagent View

### Main Agent

The main agent should reason in business operations:

- draft a quote
- ingest this supplier invoice
- attach this file
- show me the latest pricing context
- propose a new supplier

### ERP Subagent

The ERP subagent is responsible for:

- mapping those operations to ERPNext doctypes
- choosing the correct REST endpoint or allowlisted method
- enforcing approval gates
- returning clean structured results

## Error Policy

The ERP subagent must not hide ERP validation errors.

Errors should return:

- failing operation
- target doctype
- ERP validation or permission error text
- whether the operation is retryable by changing fields, or blocked pending approval or missing master data

## Idempotency And Safety

The connector should behave safely under repeated calls.

Minimum expectations:

- do not create duplicate draft documents when the same source artifact is retried without material change
- attach the original source file once and then reuse the existing file reference when possible
- avoid creating duplicate master-data proposals for the same unresolved entity

## Carry-Forward Notes

This contract deliberately stops at the semantic tool layer.

The next implementation tasks should define:

- exact request and response payloads for each tool
- exact approval artifact file layout under `/var/lib/invoice-ai/`
- exact mapping from semantic tools to ERPNext REST endpoints and allowlisted methods

The first payload layer now lives in `docs/erp-tool-schemas.md`.
