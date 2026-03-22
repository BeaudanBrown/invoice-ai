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

## Guardrails

- do not mirror structured ERP data into memory files just for convenience
- prefer concise, high-signal notes over verbose transcripts
- treat memory as operator-guidance context, not accounting truth
- memory updates are non-destructive and can be agent-managed
