# Planner Contract

The planner is the first boundary that accepts free-form operator turns.

It sits above the structured orchestrator contract and below any future richer model-routing or memory system.

## Current Tools

- `planner.plan_turn`
- `planner.handle_turn`

## Responsibilities

The planner is responsible for:

- accepting a free-form operator message
- using current `conversation_context`, especially `active_quote`
- producing a safe structured operator request
- delegating to `orchestrator.handle_request` when using `planner.handle_turn`

The planner is not responsible for:

- writing to ERPNext directly
- bypassing the orchestrator
- recreating ERP business logic

## Supported Paths Today

The current planner can map:

- supplier-document turns with explicit attachments into `supplier_document_intake`
- quote-creation turns into `quote_draft`
- quote follow-up turns with `active_quote` into `quote_revision`

The current implementation is intentionally narrow and heuristic. It exists to establish the boundary and the data flow, not to solve general natural-language planning.

## Expected Input Shape

```json
{
  "message": "Quote Acme for 2 hours onsite labour",
  "defaults": {
    "quote": {
      "company": "Test Electrical Pty Ltd",
      "currency": "AUD",
      "labor_item_code": "LAB-STD",
      "travel_item_code": "TRAVEL",
      "travel_rate": 35.0
    }
  }
}
```

For follow-up revisions:

```json
{
  "message": "Add a travel line item",
  "conversation_context": {
    "active_quote": {
      "draft_key": "quote-123",
      "quotation": "QTN-0004"
    }
  }
}
```

For supplier ingestion:

```json
{
  "message": "Process this supplier invoice",
  "attachments": [
    {
      "kind": "supplier_invoice",
      "raw_text": "Supplier: Example ..."
    }
  ]
}
```

## Next Evolution

The next iteration should plug in memory-aware and model-assisted planning while keeping the same output contract:

1. planner accepts free-form turn
2. planner emits structured operator request
3. orchestrator routes to semantic tools
4. ERP and quote logic stay in their existing delegated layers
