You are working on the `invoice-ai` hardening lane.

Read first:

1. `AGENTS.md`
2. `README.md`
3. `docs/architecture.md`
4. `docs/architecture-review-2026-03.md`
5. `docs/completion-plan.md`
6. `docs/foundation-spec.md`
7. `docs/memory.md`
8. `.loom/workstreams/hardening/context.md`
9. `.loom/workstreams/hardening/handoff.md`

Goal:

- harden the existing control plane instead of reopening foundation decisions
- keep the project self-hosted, open-source, and Nix-native
- preserve `ERPNext` as the canonical business system of record
- treat the repo-local `invoice-ai` control plane as the canonical operator-path orchestrator
- keep `n8n` optional and outside the core request path unless a later task explicitly needs it
- improve robustness, auditability, deployment readiness, and business-surface completeness

Current priority:

- turn the scaffold into a dependable first operator-facing product
