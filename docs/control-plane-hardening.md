# Control-Plane Hardening

This document records the concrete technical decisions for the next hardening step of `invoice-ai`.

## Decision Summary

1. Keep Python for v1.
2. Replace the stdlib HTTP service with `FastAPI` on an ASGI server.
3. Add a local control-plane store for operational metadata.
4. Tighten schema discipline across API, tool, and persistence boundaries.

## Why Python Stays

`invoice-ai` is mostly:

- IO-bound
- integration-heavy
- document/LLM-adjacent
- centered on ERP and artifact workflows rather than CPU-heavy computation

For that shape, Python remains a strong fit.

The main assurance problems in this repo are currently:

- loose boundaries
- missing idempotency and audit behavior
- missing durable workflow state
- incomplete testing

Changing languages would not solve those first-order problems.

## FastAPI Decision

The current service in `src/invoice_ai/service/http.py` is adequate as a scaffold but too thin for the hardening phase.

The next service boundary should move to:

- `FastAPI`
- ASGI serving
- explicit request and response models
- dependency-injected service state

Expected benefits:

- structured request validation
- cleaner auth integration
- better route organization
- easier background and job hooks
- better OpenAPI and client contract generation
- more maintainable service composition than the current stdlib handler

This does not change the higher-level architecture. It only replaces the service shell.

## Control-Plane Store Decision

The system should keep three different persistence classes:

1. `ERPNext` for canonical business records
2. filesystem paths for large artifacts and human-readable review material
3. a local queryable store for control-plane metadata

The local store should be:

- SQLite-backed for v1
- stored under `/var/lib/invoice-ai/`
- single-host and backup-friendly
- simple enough for NAS deployment without introducing another required service

## Why SQLite

SQLite is the right default here because:

- the deployment target is a single NAS host
- the service is local-first and not horizontally scaled
- the metadata volume should stay moderate
- backup and restore are simpler than adding Postgres just for control-plane state
- the repo already depends on external systems for ERP truth, so local metadata should stay operationally small

If the product later needs multi-process write contention beyond SQLite's comfort zone, or cross-host access, that is the time to revisit Postgres.

## Proposed Store Boundary

The local control-plane store should own metadata such as:

- requests
- jobs
- job events
- idempotency keys
- review records
- review decisions
- artifact references
- ingest indexes
- memory suggestion indexes

It should not own:

- canonical customer, supplier, item, quote, or invoice truth
- bulky binary artifacts
- full extracted documents when those already live on disk

## Proposed Store Layout

Recommended path:

- `/var/lib/invoice-ai/control-plane.sqlite3`

Optional future companion path:

- `/var/lib/invoice-ai/control-plane/`

## Initial Table Sketch

The exact schema can evolve, but the first shape should probably include:

- `requests`
  - request id
  - authenticated operator id
  - request kind
  - request body hash
  - created and finished timestamps
  - terminal status

- `jobs`
  - job id
  - request id
  - job kind
  - current status
  - started and finished timestamps
  - summary payload

- `job_events`
  - event id
  - job id
  - event type
  - event payload
  - created timestamp

- `idempotency_keys`
  - key
  - scope
  - bound request id
  - result fingerprint
  - expiry or retention marker

- `reviews`
  - review id
  - review kind
  - source request id
  - current status
  - target summary
  - approval artifact dir

- `review_actions`
  - review id
  - action type
  - operator id
  - note
  - created timestamp

- `artifacts`
  - artifact id
  - parent request or review id
  - artifact kind
  - filesystem path
  - content hash

- `ingest_index`
  - ingest id
  - source fingerprint
  - supplier hint
  - external invoice reference
  - linked review id
  - linked ERP draft ref

- `memory_suggestions`
  - suggestion id
  - scope
  - slug
  - status
  - linked review id

## Schema Discipline

Schema discipline means the system should stop passing freeform nested dicts across important boundaries.

The hard rule should become:

- every operator API request has a typed model
- every tool request and tool response has a typed model
- every persisted store record has a typed model
- every ERP mutation command has a typed model

## Practical Meaning

In practice this means:

1. validate before side effects
2. represent states with enums instead of ad hoc strings
3. use explicit versioned payloads where the boundary may evolve
4. keep internal convenience structures separate from public boundary contracts
5. reject malformed or partial payloads early instead of letting them drift deeper into the stack

## Recommended Modeling Split

The simplest workable split is:

- `Pydantic` models for external and persistence boundaries
- typed internal domain models where useful
- plain dicts only at the very edges of JSON serialization, not as the app's main interchange language

The current repo already has dataclass- and model-shaped code in places. The hardening step should standardize the boundary models instead of letting multiple patterns keep drifting.

The current repository conventions for this now live in `docs/schema-conventions.md`.

## Why This Helps Assurance

Stricter schemas improve assurance more directly than a language rewrite would right now because they:

- catch malformed requests before ERP writes
- make planner/orchestrator/tool contracts less ambiguous
- constrain LLM-produced structured outputs
- improve review artifact quality
- make testing much more precise

This is especially important in a financial workflow where the real risk is incorrect side effects, not raw runtime speed.
