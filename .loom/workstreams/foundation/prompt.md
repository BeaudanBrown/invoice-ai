You are working on the `invoice-ai` foundation lane.

Read first:

1. `AGENTS.md`
2. `README.md`
3. `docs/architecture.md`
4. `docs/foundation-spec.md`
5. `docs/agent-architecture.md`
6. `docs/memory.md`
7. `docs/decisions/foundation-open-questions.md`
8. `.loom/workstreams/foundation/context.md`
9. `.loom/workstreams/foundation/handoff.md`

Goal:

- keep the project self-hosted, open-source, and Nix-native
- treat `ERPNext` + `n8n` + `Ollama` + `Docling` as the current preferred stack unless a documented decision changes that
- prefer native `ERPNext` APIs and document models over app-local reimplementation
- produce durable docs and implementation-ready decisions rather than vague brainstorming
- preserve a clean import path into `nix-dotfiles` as `nixosModules.invoice-ai`

Current priority:

- solidify the first implementation slice and the deployment contract

Beads references:

- epic `coordinator-326`
- `coordinator-326.9`
- `coordinator-326.10`
- `coordinator-326.11`
