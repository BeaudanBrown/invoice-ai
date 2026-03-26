# NixOS Module Contract

This document defines the current `services.invoice-ai` composition for NAS hosting.

## Design Decision

The implemented module now owns:

- the `invoice-ai` control-plane service
- an embedded `ERPNext` stack deployed through OCI containers
- its persistent application directories under `/var/lib/invoice-ai/`
- its runtime user/group
- its listen address and port
- its dependency endpoints and secret file wiring

For rollout safety, the module supports two ERP modes:

- `external`: connect to an existing ERPNext deployment
- `embedded`: deploy ERPNext inside the same module boundary

`embedded` mode is the primary NAS deployment path.

The module still does not need to own:

- `Ollama` lifecycle
- `Docling` lifecycle
- `n8n` lifecycle
- reverse proxy and TLS
- host backup policy

Those remain host-level concerns in `nix-dotfiles`, even though this repo exposes the interface for connecting to them.

## First Composition Boundary

The service boundary is:

1. one `invoice-ai` application service
2. one ERP lane, either external or embedded
3. one persistent state root for `invoice-ai`
4. explicit persistent roots for ERPNext site and database state
5. a set of configured dependency endpoints

This keeps the module deployable as one product boundary while still allowing OCI-based ERPNext deployment now.

## Repo-Owned Interface

The repo should export a stable module namespace:

- `services.invoice-ai.enable`
- `services.invoice-ai.package`
- `services.invoice-ai.user`
- `services.invoice-ai.group`
- `services.invoice-ai.listenAddress`
- `services.invoice-ai.port`
- `services.invoice-ai.publicUrl`
- `services.invoice-ai.operatorAuth.tokensFile`
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

The `services.invoice-ai.erpnext.*` subtree now covers:

- `mode`
- `credentialsFile`
- `url`
- `publicUrl`
- `siteName`
- `siteHost`
- `image`
- `version`
- `backendPort`
- `frontendPort`
- `websocketPort`
- `database.*`
- `redis.*`
- `volumes.*`
- `secrets.*`

## Host-Owned Inputs In `nix-dotfiles`

These values should stay host-specific:

- actual hostnames and reverse-proxy routing
- secret files and credentials
- whether ERPNext runs embedded or external during migration
- backup policy
- storage device layout
- firewall policy

## Dependency Contract

### ERPNext

Required for real operation.

Expected external-mode inputs:

- base URL
- credential file for API access

Expected embedded-mode inputs:

- ERPNext/Frappe image and version selection
- MariaDB and Redis wiring
- site name and public hostname
- bootstrap credentials
- persistent site, log, database, and Redis volumes

### Ollama

Expected to be available as an HTTP endpoint.

Expected inputs:

- base URL

### Docling

May eventually be embedded, but the module should initially treat it as a configurable dependency endpoint.

Expected inputs:

- base URL

### n8n

Optional integration only.

Expected inputs:

- base URL

The core control plane should not depend on `n8n` for the primary operator path. If `n8n` is used later, it should sit at the edges for automation, scheduling, or integration work rather than replace the repo-local planner/orchestrator.

## Runtime Shape

The combined deployment exposes:

- one HTTP control-plane API on the configured address and port
- one ERPNext frontend on its configured internal address and port
- the internal ERPNext backend, websocket, worker, scheduler, MariaDB, and Redis services required to keep the embedded stack operational
- one-shot bootstrap units for network creation, MariaDB env preparation, bench configuration, site creation, and stable site config application

Current endpoints:

- `GET /healthz`
- `GET /api/runtime`
- `POST /api/tools/run`
- `GET /api/requests`
- `GET /api/requests/{request_id}`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/reviews`
- `GET /api/reviews/{review_id}`
- `GET /docs`
- `GET /openapi.json`

The service process is started with:

- `${package}/bin/invoice-ai serve-http`

The module also runs:

- `${package}/bin/invoice-ai init-paths`

as `ExecStartPre` so the runtime directory contract is exercised through the module boundary before the service starts.

The module is ready for future expansion into:

- a background worker
- scheduled maintenance or cleanup jobs
- ERPNext backup/export hooks
- ERPNext migration and service-user bootstrap units

The current implementation already uses separate bootstrap units for site bring-up; service-user bootstrap is still pending.

## Current Systemd Contract

When `services.invoice-ai.enable = true;` the module provisions:

- a dedicated `invoice-ai` system user and group by default
- tmpfiles rules for the persistent runtime directories
- a `systemd.services.invoice-ai` unit
- the runtime environment variables consumed by `RuntimeConfig.from_env()`
- optional host-provided secret loading through `services.invoice-ai.environmentFile`
- when `erpnext.mode = "embedded"`, the ERPNext OCI services, persistent volumes, and bootstrap jobs needed to make the embedded stack usable

## Secret Wiring

The module prefers one environment file path owned by the host:

- `services.invoice-ai.environmentFile`

The operator API also expects a host-provided bearer token file:

- `services.invoice-ai.operatorAuth.tokensFile`

That file can hold or point to:

- ERPNext API token
- operator bearer tokens for the FastAPI surface
- future service credentials

The repo should define the contract; `nix-dotfiles` should provide the actual secret material.

For the combined deployment, the required secret groups are treated separately:

1. `invoice-ai` control-plane secrets
   - operator bearer tokens
   - optional environment overrides
   - ERPNext service-user credentials for the control plane
2. ERPNext bootstrap secrets
   - site admin password
   - MariaDB credentials
   - site encryption key

The host should populate those secrets through `sops`. The module consumes them as host-provided files and turns them into:

- `/run/invoice-ai-erpnext/mariadb.env` for the MariaDB container
- `bench new-site` bootstrap arguments for the default ERPNext site
- `bench --site <site> set-config` calls for `encryption_key` and optional `host_name`

The `invoice-ai` ERP service-user API credential file is still a host-populated post-bootstrap secret rather than an automatically generated output.

## Why This Boundary

This boundary keeps the repo Nix-native without overcommitting to packaging every dependency immediately.

It also preserves the key product requirement:

- from the operator perspective, there is still one `invoice-ai` service surface

while keeping operational reality manageable on the NAS.
