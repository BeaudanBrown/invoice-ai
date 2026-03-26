# Architecture

## Objective

Build a self-hosted quoting and invoicing platform that can draft outbound quotes and invoices from natural-language job descriptions and continuously improve pricing knowledge by ingesting inbound supplier invoices and receipts.

## Working Architecture Direction

The current architecture direction is:

- `ERPNext` as the canonical system of record for customers, items/services, taxes, sales invoices, purchase invoices, and price history
- the repo-local `invoice-ai` control plane as the canonical planner/orchestrator/review surface
- `Ollama` for local LLM inference when model assistance is useful
- `Docling` for structured document extraction from supplier invoices and receipts
- optional external automation tools such as `n8n`, kept outside the core request path unless a later integration needs them

This reflects the implemented system more accurately than the original foundation stack notes. The repo now already contains its own control plane, so external workflow tools should be treated as integrations, not as the primary orchestrator.

## Core Capabilities

### Natural-Language Quote And Invoice Drafting

Input example:

> quote Acme for an emergency switchboard repair, 3 hours onsite, one replacement switch, and travel

Target flow:

1. resolve the client and relevant job context
2. retrieve similar historical invoices, line items, and pricing rules
3. propose invoice lines, quantities, tax treatment, and notes
4. create or revise a draft quote or invoice in ERPNext using native APIs
5. show a review step before any approval-gated action
6. generate a PDF artifact plus structured intermediates for operator review

### Supplier Invoice Ingestion

Target flow:

1. ingest PDF, email, or scan
2. extract structured fields and line items
3. normalize supplier identity and purchased items/services
4. update purchase history and pricing intelligence through ERP-first flows
5. surface anomalies, duplicates, and confidence gaps for review

## Operating Rules

- the user-facing experience is one main chat agent
- the main agent delegates to narrower instruction-driven subagents
- `ERPNext` is the primary operational memory for customers, suppliers, items, quotes, invoices, and prices
- markdown memory is reserved for fluid natural-language instructions and relationship context
- if `ERPNext` already supports a capability, prefer its API and document model over app-local reimplementation
- destructive actions and final submission require approval
- new master data creation requires approval

## Architectural Constraints

- fully self-hosted
- open-source components only for the core stack
- Nix-native packaging and deployment from the start
- deployable as a NixOS module on the NAS through `nix-dotfiles`
- no dependence on coordinator-local state for implementation logic

## Primary Specs

- `docs/foundation-spec.md`
- `docs/architecture-review-2026-03.md`
- `docs/completion-plan.md`
- `docs/control-plane-hardening.md`
- `docs/erpnext-entity-map.md`
- `docs/erp-tool-contract.md`
- `docs/erp-tool-schemas.md`
- `docs/agent-architecture.md`
- `docs/memory.md`
- `docs/nixos-module-contract.md`
- `docs/storage-layout.md`
- `docs/vertical-slice-1.md`
- `docs/implementation-plan-1.md`
- `docs/decisions/foundation-open-questions.md`
