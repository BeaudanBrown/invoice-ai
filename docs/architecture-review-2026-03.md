# Architecture Review 2026-03

This review captures the current implemented architecture, the strongest parts of the system, the main weaknesses, and the decisions that should govern the next phase of work.

## Summary

The current architecture is good enough to keep. The main problem is not architectural confusion anymore. The main problem is uneven completeness.

The repo already has a coherent control-plane split:

- planner
- orchestrator
- ERP semantic tools
- extraction and ingest
- quote drafting
- memory
- approvals, revisions, and artifacts
- Nix-native service packaging

That is a solid base. The weak sections are mostly about product completion, service hardening, and operational rigor.

## Strong Sections

### ERP-First Boundary

`ERPNext` is correctly treated as the canonical system of record for customers, suppliers, items, quotations, purchase invoices, taxes, and pricing history.

This is the right boundary. It avoids a shadow ERP inside the app.

### Layered Control Plane

The repo has a defensible separation between:

- free-form planning
- structured operator requests
- domain-specific tool execution
- durable review and artifact storage

That is the right shape for a chat-first operator system.

### Approval And Review Posture

The system already has explicit approval objects, approval artifacts, and review-gated memory changes. That is much safer than burying important decisions in chat.

### Nix-Native Deployment Direction

The project is already packaged as a flake with a NixOS module boundary. That keeps deployment design from drifting away from the real hosting target.

## Weak Sections

### 1. Control Plane Is Not Hardened Yet

The service in `src/invoice_ai/service/http.py` is still a thin tool-execution API. It is missing:

- authentication
- explicit operator/session identity
- structured audit events
- idempotency guards for write requests
- long-running workflow tracking

This is the biggest runtime weakness.

The concrete hardening direction for this section is now:

- keep Python for v1
- replace the service shell with `FastAPI`
- add a local SQLite-backed control-plane store
- tighten typed boundary models instead of relying on freeform dict traffic

### 2. Sales-Invoice Path Is Missing

The repo can draft quotations and ingest supplier purchase invoices, but it still cannot complete the main outbound invoice story on the accounts-receivable side.

That leaves the product structurally incomplete.

### 3. ERP Semantic Coverage Is Still Narrow

The ERP semantic tool layer is good in style but still small in surface area. It needs broader support for:

- sales invoices
- quote-to-invoice conversion
- master-data proposal and approval flows
- richer tax, pricing, and item handling
- document lifecycle actions with proper approval boundaries

### 4. Extraction Is Still Thin

The extraction path is adequate for the first slice, but it is not yet robust enough for real supplier-document handling. Missing pieces include:

- stronger confidence scoring
- duplicate detection
- better line-item normalization
- better separation between extraction and classification
- stronger support for images and non-trivial PDFs

### 5. Review Actions Are Incomplete

The system can list review items and inspect some memory review data, but the operator-facing surface is still not complete enough to handle full inspect and accept/reject flows consistently across review types.

### 6. Testing And Deployment Proof Are Too Light

The current checks are useful, but they are still mostly scaffold-grade:

- `nix flake check`
- compile checks
- mocked ERP flows

What is missing is a disposable end-to-end verification path that exercises the real service against a realistic stack.

## Decisions For The Next Phase

### Decision 1: The Repo-Local Control Plane Is Canonical

The implemented planner, orchestrator, and tool-execution layers are now the primary orchestration surface.

`n8n` is no longer a core dependency for the request path. It should be treated as an optional integration point for later external automation, scheduling, or side-effectful workflows that do not belong in the core synchronous control plane.

### Decision 2: Add A First-Class Job And Audit Layer

The next runtime hardening step should introduce persistent jobs and audit events under the application state tree.

The control plane should stop behaving like a generic tool runner and start behaving like an operator service with:

- request receipts
- job state
- event logs
- stable references for approvals and artifacts

The local metadata store for this should be SQLite-backed rather than purely filesystem-shaped.

### Decision 3: Complete The Business Surface Before Making Planning More Clever

The next major business completion step should be sales-invoice support, not more planner sophistication.

The planner is only as useful as the safe structured tool surface beneath it.

### Decision 4: Keep Review Uniform Across Domains

Memory review, master-data review, quote/invoice submission review, and destructive-action review should converge on one common review model with:

- indexed review records
- inspectable payloads
- accept/reject actions
- artifact refs
- audit history

### Decision 5: Prefer Deterministic Extraction Pipelines Over Prompt-Only Extraction

Raw-document ingestion should stay schema-first and confidence-aware.

The control plane should use:

- deterministic extraction where possible
- model assistance where helpful
- explicit uncertainty fields rather than silent best-effort writes

### Decision 6: Tighten Schema Discipline Instead Of Rewriting Languages

The next assurance step should be stricter boundary modeling rather than a language rewrite.

The current plan is:

- keep Python for v1
- move the operator API to `FastAPI`
- introduce typed request, response, and persistence models
- reduce freeform dict traffic across module boundaries

See `docs/control-plane-hardening.md`.

## Implementation Consequences

These decisions imply the following roadmap:

1. harden the operator service with auth, jobs, audit, and idempotency
2. complete quote/invoice business coverage on the ERP side
3. finish the operator review surface
4. strengthen extraction and duplicate-safe ingest
5. add end-to-end deployment and verification

## Non-Decision

This review does not change the core ERP-first rule, the approval boundaries, or the choice to keep mutable natural-language memory outside git.
