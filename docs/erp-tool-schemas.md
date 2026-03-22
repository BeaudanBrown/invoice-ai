# ERP Tool Schemas

This document defines the first request and response payload schemas for the semantic ERP tools.

It is intentionally scoped to the tools needed to begin connector implementation for the first vertical slice. Additional tools can extend the same envelope later.

## Common Request Envelope

Every tool request should use this outer shape:

```json
{
  "request_id": "uuid-or-stable-id",
  "tool_name": "erp.get_doc",
  "dry_run": false,
  "conversation_context": {
    "session_id": "optional-session-id",
    "user_intent": "brief summary of what the user asked for"
  },
  "payload": {}
}
```

Rules:

- `request_id` must be caller-generated and stable for retries
- `tool_name` identifies the semantic tool, not a raw endpoint
- `dry_run` should be `true` when the caller wants planning or validation without a write

## Common Response Envelope

Every tool response should use this outer shape:

```json
{
  "request_id": "uuid-or-stable-id",
  "tool_name": "erp.get_doc",
  "status": "success",
  "data": {},
  "errors": [],
  "warnings": [],
  "approval": null,
  "meta": {}
}
```

Allowed `status` values:

- `success`
- `approval_required`
- `validation_error`
- `not_found`
- `blocked`
- `error`

Rules:

- `data` contains the normal result payload
- `errors` contains machine-usable failures
- `warnings` contains non-fatal issues
- `approval` is non-null only when an approval-gated action is proposed instead of executed

## Approval Object

When `status = "approval_required"`, the response must include:

```json
{
  "approval_id": "approval-uuid",
  "action": "create_supplier",
  "summary": "Create new supplier from ingested invoice",
  "target": {
    "doctype": "Supplier",
    "name": null
  },
  "proposed_changes": {},
  "artifacts": {
    "summary_markdown_path": "/var/lib/invoice-ai/approvals/.../summary.md",
    "request_json_path": "/var/lib/invoice-ai/approvals/.../request.json",
    "diff_json_path": "/var/lib/invoice-ai/approvals/.../diff.json"
  }
}
```

## Shared Field Shapes

### ERP Reference

```json
{
  "doctype": "Quotation",
  "name": "QTN-0001"
}
```

### Attachment Reference

```json
{
  "file_name": "supplier-invoice.pdf",
  "file_url": "/files/supplier-invoice.pdf"
}
```

### Source Reference

```json
{
  "source_type": "upload",
  "source_path": "/var/lib/invoice-ai/ingest/processed/.../source.pdf",
  "source_hash": "sha256:..."
}
```

## Read Tools

### `erp.get_doc`

Request payload:

```json
{
  "doctype": "Customer",
  "name": "CUST-0001",
  "fields": ["name", "customer_name", "customer_group"]
}
```

Success `data`:

```json
{
  "doc": {
    "doctype": "Customer",
    "name": "CUST-0001",
    "customer_name": "Acme Electrical",
    "customer_group": "Commercial"
  }
}
```

### `erp.list_docs`

Request payload:

```json
{
  "doctype": "Quotation",
  "filters": {
    "party_name": "Acme Electrical",
    "docstatus": 0
  },
  "fields": ["name", "transaction_date", "grand_total"],
  "order_by": "modified desc",
  "limit": 20
}
```

Success `data`:

```json
{
  "docs": [
    {
      "name": "QTN-0004",
      "transaction_date": "2026-03-20",
      "grand_total": 842.50
    }
  ]
}
```

### `erp.get_linked_context`

Request payload:

```json
{
  "subject": {
    "doctype": "Customer",
    "name": "CUST-0001"
  },
  "include": [
    "quotations",
    "sales_invoices",
    "projects",
    "pricing_context"
  ],
  "limit_per_relation": 10
}
```

Success `data`:

```json
{
  "subject": {
    "doctype": "Customer",
    "name": "CUST-0001"
  },
  "linked": {
    "quotations": [],
    "sales_invoices": [],
    "projects": [],
    "pricing_context": {}
  }
}
```

### `erp.get_pricing_context`

Request payload:

```json
{
  "items": [
    {
      "item_code": "LABOUR-ELEC-STD"
    },
    {
      "item_code": "SWITCH-REPLACEMENT"
    }
  ],
  "customer": "CUST-0001",
  "supplier": null
}
```

Success `data`:

```json
{
  "items": [
    {
      "item_code": "LABOUR-ELEC-STD",
      "price_list_rates": [],
      "pricing_rules": [],
      "recent_sales": [],
      "recent_purchases": []
    }
  ]
}
```

## Draft Mutation Tools

### `erp.create_draft_quotation`

Request payload:

```json
{
  "customer": "CUST-0001",
  "company": "My Company",
  "currency": "AUD",
  "items": [
    {
      "item_code": "LABOUR-ELEC-STD",
      "qty": 3,
      "rate": 120.0,
      "description": "Emergency electrical labor"
    },
    {
      "item_code": "SWITCH-REPLACEMENT",
      "qty": 1,
      "rate": 85.0,
      "description": "Replacement switch"
    }
  ],
  "narrative": {
    "intro": "Emergency switchboard repair quote",
    "notes": "Travel included"
  },
  "source_refs": []
}
```

Success `data`:

```json
{
  "doc_ref": {
    "doctype": "Quotation",
    "name": "QTN-0005"
  },
  "docstatus": 0
}
```

### `erp.update_draft_quotation`

Request payload:

```json
{
  "quotation": "QTN-0005",
  "patch": {
    "items": [
      {
        "item_code": "LABOUR-ELEC-STD",
        "qty": 4,
        "rate": 120.0,
        "description": "Emergency electrical labor"
      }
    ],
    "replace_items": false,
    "notes_append": [
      "Revised labor from 3 to 4 hours"
    ]
  }
}
```

Success `data`:

```json
{
  "doc_ref": {
    "doctype": "Quotation",
    "name": "QTN-0005"
  },
  "docstatus": 0
}
```

### `erp.create_draft_purchase_invoice`

Request payload:

```json
{
  "supplier": "SUPP-0003",
  "bill_no": "INV-9012",
  "posting_date": "2026-03-23",
  "items": [
    {
      "item_code": "SWITCH-REPLACEMENT",
      "qty": 1,
      "rate": 55.0,
      "description": "Supplier switch replacement item"
    }
  ],
  "source_ref": {
    "source_type": "upload",
    "source_path": "/var/lib/invoice-ai/ingest/processed/.../source.pdf",
    "source_hash": "sha256:..."
  }
}
```

Success `data`:

```json
{
  "doc_ref": {
    "doctype": "Purchase Invoice",
    "name": "ACC-PINV-0007"
  },
  "docstatus": 0
}
```

Approval-required response:

```json
{
  "request_id": "req-1",
  "tool_name": "erp.create_draft_purchase_invoice",
  "status": "approval_required",
  "data": {},
  "errors": [],
  "warnings": [
    "Supplier match confidence too low for direct ERP write"
  ],
  "approval": {
    "approval_id": "approval-1",
    "action": "create_supplier",
    "summary": "Approve creation of a new supplier before purchase invoice drafting",
    "target": {
      "doctype": "Supplier",
      "name": null
    },
    "proposed_changes": {
      "supplier_name": "Example Supplier Pty Ltd"
    },
    "artifacts": {
      "summary_markdown_path": "/var/lib/invoice-ai/approvals/approval-1/summary.md",
      "request_json_path": "/var/lib/invoice-ai/approvals/approval-1/request.json",
      "diff_json_path": "/var/lib/invoice-ai/approvals/approval-1/diff.json"
    }
  },
  "meta": {}
}
```

### `erp.attach_file`

Request payload:

```json
{
  "target": {
    "doctype": "Purchase Invoice",
    "name": "ACC-PINV-0007"
  },
  "source_path": "/var/lib/invoice-ai/ingest/processed/.../source.pdf",
  "file_name": "source.pdf",
  "is_private": true
}
```

Success `data`:

```json
{
  "target": {
    "doctype": "Purchase Invoice",
    "name": "ACC-PINV-0007"
  },
  "attachment": {
    "file_name": "source.pdf",
    "file_url": "/private/files/source.pdf"
  }
}
```

## Approval-Gated Mutation Tools

These tools use the same outer envelope but usually return `approval_required` before execution.

### `erp.create_customer`
### `erp.create_supplier`
### `erp.create_item`
### `erp.create_or_update_pricing_rule`
### `erp.submit_doc`
### `erp.cancel_doc`
### `erp.amend_doc`

Shared request payload shape:

```json
{
  "target": {
    "doctype": "Supplier",
    "name": null
  },
  "fields": {
    "supplier_name": "Example Supplier Pty Ltd"
  }
}
```

If already approved and executed, success `data` should at minimum contain:

```json
{
  "doc_ref": {
    "doctype": "Supplier",
    "name": "SUPP-0004"
  },
  "docstatus": 0
}
```

## Error Shape

When the ERP rejects a request:

```json
{
  "request_id": "req-1",
  "tool_name": "erp.create_draft_quotation",
  "status": "validation_error",
  "data": {},
  "errors": [
    {
      "code": "erp.validation",
      "message": "Item code LABOUR-ELEC-STD is missing"
    }
  ],
  "warnings": [],
  "approval": null,
  "meta": {
    "retryable": true
  }
}
```

## First-Slice Minimum Tool Set

The first code-facing connector only needs to implement:

- `erp.get_doc`
- `erp.list_docs`
- `erp.get_linked_context`
- `erp.get_pricing_context`
- `erp.create_draft_purchase_invoice`
- `erp.create_draft_quotation`
- `erp.update_draft_quotation`
- `erp.attach_file`

Everything else can remain specified-but-unimplemented until the first loop works.
