# Schema Conventions

`invoice-ai` now treats boundary schemas as a first-class control-plane concern.

## Modeling Stack

Use `Pydantic` models for:

- operator API request and response bodies
- tool request and response envelopes
- semantic ERP command payloads
- persisted control-plane and file-backed record shapes

Use plain Python dicts only:

- at JSON serialization edges
- inside intentionally open-ended payload fields
- for raw third-party responses before they are normalized

## Current Canonical Boundary Models

The main schema entrypoints are:

- `src/invoice_ai/erp/schemas.py`
  - `ToolRequest`
  - `ToolResponse`
  - `ApprovalPayload`
  - `ToolExecutionStatus`
- `src/invoice_ai/erp/commands.py`
  - typed semantic ERP command payloads
- `src/invoice_ai/service/models.py`
  - current operator HTTP request and response bodies
- `src/invoice_ai/orchestrator/models.py`
  - operator request routing contract
- `src/invoice_ai/planner/models.py`
  - planner turn contract
- `src/invoice_ai/persistence.py`
  - file-backed ingest and revision record shapes

## Rules

1. Validate before side effects.
2. Prefer enums over ad hoc status strings.
3. Keep payload evolution at explicit boundary modules.
4. Let executors consume typed commands instead of reaching directly into nested dicts.
5. Keep request/response serialization stable through `model_dump(mode="json")`.

## Practical Guidance

When adding a new tool or service route:

1. add or extend the boundary model first
2. validate the request at the edge
3. convert into narrower command models before calling ERP or persistence code
4. return a typed response envelope

When adding new persistence:

1. define the persisted record shape in `src/invoice_ai/persistence.py` or a successor store module
2. write that typed record to disk or the future SQLite store
3. keep filesystem artifacts separate from queryable metadata

## Current Limits

This schema pass does not yet replace every internal dict in the repo. It intentionally hardens the public and side-effecting seams first. Remaining deeper refactors should preserve that direction instead of introducing new ad hoc payload paths.
