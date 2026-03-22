# NixOS Module Contract

This document defines the first concrete `services.invoice-ai` composition for NAS hosting.

## Design Decision

For the first implementation, the NixOS module owns:

- the `invoice-ai` control-plane service
- its persistent application directories under `/var/lib/invoice-ai/`
- its runtime user/group
- its listen address and port
- its dependency endpoints and secret file wiring

For the first implementation, the NixOS module does not own:

- `ERPNext` deployment
- MariaDB or Redis for `ERPNext`
- `Ollama` lifecycle
- `Docling` lifecycle
- `n8n` lifecycle
- reverse proxy and TLS
- host backup policy

Those remain host-level concerns in `nix-dotfiles`, even though this repo exposes the interface for connecting to them.

## First Composition Boundary

The service boundary is:

1. one `invoice-ai` application service
2. one persistent state root
3. a set of configured dependency endpoints

This keeps the first module narrow enough to wire on the NAS without blocking on packaging or operating the whole stack in one shot.

## Repo-Owned Interface

The repo should export a stable module namespace:

- `services.invoice-ai.enable`
- `services.invoice-ai.package`
- `services.invoice-ai.user`
- `services.invoice-ai.group`
- `services.invoice-ai.listenAddress`
- `services.invoice-ai.port`
- `services.invoice-ai.publicUrl`
- `services.invoice-ai.stateDir`
- `services.invoice-ai.documentsDir`
- `services.invoice-ai.memoryDir`
- `services.invoice-ai.ingestDir`
- `services.invoice-ai.approvalsDir`
- `services.invoice-ai.revisionsDir`
- `services.invoice-ai.artifactsDir`
- `services.invoice-ai.cacheDir`
- `services.invoice-ai.environmentFile`
- `services.invoice-ai.erpnext.*`
- `services.invoice-ai.ollama.*`
- `services.invoice-ai.docling.*`
- `services.invoice-ai.n8n.*`

## Host-Owned Inputs In `nix-dotfiles`

These values should stay host-specific:

- actual hostnames and reverse-proxy routing
- secret files and credentials
- whether dependencies run on the same host or elsewhere
- backup policy
- storage device layout
- firewall policy

## Dependency Contract

### ERPNext

Required for real operation.

Expected inputs:

- base URL
- credential file for API access

### Ollama

Expected to be available as an HTTP endpoint.

Expected inputs:

- base URL

### Docling

May eventually be embedded, but the module should initially treat it as a configurable dependency endpoint.

Expected inputs:

- base URL

### n8n

Optional in the first runnable slice.

Expected inputs:

- base URL

The first implementation should not require `n8n` just to make the core chat-to-ERP loop work.

## Runtime Shape

The first application service should eventually expose:

- one HTTP API / chat backend on the configured address and port

The module should be ready for future expansion into:

- a background worker
- scheduled maintenance or cleanup jobs

But those do not need to be separate systemd units yet.

## Secret Wiring

The module should prefer one environment file path owned by the host:

- `services.invoice-ai.environmentFile`

That file can hold or point to:

- ERPNext API token
- future service credentials

The repo should define the contract; `nix-dotfiles` should provide the actual secret material.

## Why This Boundary

This boundary keeps the repo Nix-native without overcommitting to packaging every dependency immediately.

It also preserves the key product requirement:

- from the operator perspective, there is still one `invoice-ai` service surface

while keeping operational reality manageable on the NAS.
