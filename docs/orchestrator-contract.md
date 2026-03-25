# Orchestrator Contract

The operator-facing orchestrator is the first stable boundary between chat-like interaction and the lower-level semantic tools.

## Current Envelope

The current top-level tool is:

- `orchestrator.handle_request`

It accepts a structured operator request envelope with one of these request kinds:

- `supplier_document_intake`
- `quote_draft`
- `quote_revision`

The orchestrator is responsible for:

- classifying or accepting the request kind
- routing to the correct delegated tool family
- returning one normalized response shape with stage, artifacts, ERP refs, and delegated response details

The orchestrator is not responsible for:

- parsing natural language into ERP mutations
- duplicating ERPNext business logic
- mutating ERP state directly without using the semantic tool layer

## Quote Conversation State

For quote-related requests, the orchestrator returns:

- `data.conversation_state.active_quote`

That state contains:

- `draft_key`
- `quotation`
- `latest_revision_id`
- `preview_path`

Follow-up quote edits should reuse that state through:

- `conversation_context.active_quote`

This lets the chat-planning layer keep draft identity across turns without making the lower-level quote tool guess which draft is being revised.

## Transition To Chat Planning

The next planner layer should convert raw operator chat into the structured orchestrator envelopes above.

The intended boundary is:

1. planner interprets chat
2. planner emits a structured orchestrator request
3. orchestrator routes to existing semantic tools
4. ERP-side writes remain inside the current semantic ERP and quote tool layers

That means free-form chat should eventually terminate in envelopes like:

```json
{
  "request_kind": "quote_revision",
  "message": "split travel onto its own line",
  "patch": {
    "items": [
      {
        "item_code": "TRAVEL",
        "qty": 1,
        "rate": 35.0,
        "description": "Travel"
      }
    ],
    "replace_items": false
  },
  "summary": "Add a separate travel line item"
}
```

while the planner reuses:

```json
{
  "conversation_context": {
    "active_quote": {
      "draft_key": "quote-123",
      "quotation": "QTN-0004"
    }
  }
}
```

## Design Rule

As the planner gets smarter, the orchestrator should stay thin.

It should keep normalizing routing, conversation state, and response shape, while the existing delegated tools remain the only code that knows how to create or revise ERP-backed drafts.
## Supported Request Kinds

The orchestrator currently accepts these operator request kinds:

- `supplier_document_intake`
- `review_queue`
- `quote_draft`
- `quote_revision`

`review_queue` currently delegates to `memory.list_reviews`, which lets the main operator-facing surface answer pending memory-review questions without exposing the lower-level memory tool family directly.
