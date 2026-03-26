# invoice-ai Agent Guide

This repository is a Nix-native project for building a self-hosted AI-assisted invoicing platform.

## Read Order

1. This file
2. `README.md`
3. `docs/architecture.md`
4. `docs/architecture-review-2026-03.md`
5. `docs/completion-plan.md`
6. `docs/control-plane-hardening.md`
7. `docs/decisions/foundation-open-questions.md`
8. `.loom/workstreams/<workstream>/context.md`
9. `.loom/workstreams/<workstream>/handoff.md`

## Repository Shape

- `flake.nix` is the primary packaging and hosting contract.
- `modules/invoice-ai.nix` is the stable NixOS module entrypoint intended for import from `nix-dotfiles`.
- `docs/` holds the durable architecture and decision record.
- `.loom/workstreams/` holds resumable execution context for coordinator-managed work.

## Working Rules

- Keep the project fully self-hosted and Nix-native by default.
- Prefer local/open models and local services over hosted APIs unless a decision record explicitly approves an exception.
- Treat invoice generation as a reviewed workflow, not an autonomous fire-and-forget action, until the approval boundary is deliberately changed.
- Capture unresolved product and architecture questions in Beads and durable docs rather than in ad hoc notes.
- Treat the repo-local `invoice-ai` control plane as the canonical operator-path orchestrator; external tools such as `n8n` are optional integrations, not the primary runtime.
- If the NixOS service contract changes, update `flake.nix`, `modules/invoice-ai.nix`, and the relevant docs in the same task.

## Nix Hosting Contract

- Keep `nixosModules.default` aligned with `nixosModules.invoice-ai`.
- Keep the service namespace under `services.invoice-ai`.
- Design the module so `nix-dotfiles` can import this repo directly as a flake input without patching local paths.
- Keep deployment assumptions NAS-friendly: persistent state directories, reverse-proxy readiness, and declarative secret wiring points.

## Verification

- Run `nix flake check` for any Nix-facing change.
- If module behavior changes, verify with a targeted `nix eval` or `nix build` path in addition to `nix flake check`.
- When the application layer exists, document the canonical local verification path here.
