# Memory

## Purpose

Memory in this project is for fluid natural-language context that should guide the agent but does not belong as canonical business data inside `ERPNext`.

Examples:

- client-specific preferences
- operator instructions
- job-pattern preferences
- relationship context
- exceptions such as informal discounts or preferred phrasing

Structured operational facts should remain in `ERPNext`.

## Storage Direction

The memory store should live in persistent application-owned storage exposed by the NixOS module, likely under:

- `/var/lib/invoice-ai/`

The exact on-disk layout can evolve, but it should be:

- durable across deploys
- readable by the application service
- separate from immutable repo content

The first concrete storage layout now lives in `docs/storage-layout.md`.

The first implementation now also supports lightweight markdown frontmatter for planner consumption. Useful keys include:

- `subject`
- `canonical_customer`
- `customer_name`
- `quote_defaults`
- `labor_item_code`
- `travel_item_code`
- `travel_rate`

## Memory Types

### Operator Memory

Examples:

- pricing preference instructions
- tone or phrasing preferences
- review/approval habits

### Client Memory

Examples:

- client gets a standing discount
- client prefers simplified descriptions
- client expects itemized materials

### Job Memory

Examples:

- specific site constraints
- recurring wording or scope patterns
- approval or quoting preferences tied to a job type

### Supplier Memory

Examples:

- recurring supplier naming quirks
- invoice formatting or labeling habits that help ingestion review
- known exceptions that matter for future purchase-invoice normalization

## Guardrails

- do not mirror structured ERP data into memory files just for convenience
- prefer concise, high-signal notes over verbose transcripts
- treat memory as operator-guidance context, not accounting truth
- memory updates should be proposed first and only applied after explicit review

## Tool Surface

The first explicit memory tools now live under `src/invoice_ai/memory/`:

- `memory.list_documents`
- `memory.get_document`
- `memory.upsert_document`
- `memory.record_note`
- `memory.list_reviews`
- `memory.get_review`
- `memory.list_suggestions`
- `memory.get_suggestion`
- `memory.suggest_update`
- `memory.accept_suggestion`
- `memory.reject_suggestion`

These tools are intended to keep memory management explicit and auditable while reusing the same markdown store the planner reads.

## Suggestion Workflow

Memory suggestions should be review-gated by default:

1. the system proposes a structured memory suggestion
2. the suggestion is persisted separately from durable markdown memory
3. the operator reviews and accepts or rejects it
4. only accepted suggestions are written into the markdown memory store

The first implementation stores suggestions alongside memory under the persistent application state tree and reuses the general approval artifact flow so suggestion proposals can be inspected with the same review tooling as other gated actions.

Planner-generated memory reviews now also write those approval artifacts eagerly, so operator chat flows and mixed quote/intake flows both leave durable review records under the approvals tree.

The memory layer now also exposes a simple review index over those records so callers can enumerate pending or accepted memory reviews and inspect their artifact paths and summary preview without walking the approvals directory directly.

The planner can now also surface these suggestions from explicit operator turns, including:

- pure conversational memory capture such as `remember client Acme prefers itemized materials`
- quote drafting or revision turns that include a durable instruction
- supplier intake turns that include a review note worth retaining for later ingestion
