# Deployment Secrets

This document defines the first secret inventory for deploying `invoice-ai` as one module that can also embed `ERPNext`.

## Scope

The target deployment shape is:

- one `invoice-ai` NixOS module
- one `invoice-ai` control-plane service
- optional embedded `ERPNext` deployment through OCI containers

Secrets should be grouped by function so the host can populate them clearly through `sops`.

## Secret Groups

### 1. invoice-ai Control Plane

These secrets are required for the AI-facing service itself.

Suggested `sops` keys:

- `invoice-ai.env`
- `invoice-ai.operator-tokens`
- `invoice-ai.erpnext-credentials`

Expected purpose:

- `invoice-ai.env`
  - optional environment overrides such as `INVOICE_AI_OLLAMA_URL` or `INVOICE_AI_N8N_URL`
- `invoice-ai.operator-tokens`
  - bearer tokens for the FastAPI operator surface
- `invoice-ai.erpnext-credentials`
  - the ERPNext API credentials used by the control plane's service account

### 2. ERPNext Bootstrap

These secrets are required when `services.invoice-ai.erpnext.mode = "embedded"`.

Suggested `sops` keys:

- `invoice-ai/erpnext-db-root-password`
- `invoice-ai/erpnext-db-password`
- `invoice-ai/erpnext-admin-password`
- `invoice-ai/erpnext-frappe-secret-key`

Expected purpose:

- `invoice-ai/erpnext-db-root-password`
  - MariaDB root password used during bootstrap and maintenance
- `invoice-ai/erpnext-db-password`
  - password for the default ERPNext site database user created during `bench new-site`
- `invoice-ai/erpnext-admin-password`
  - initial ERPNext Administrator password or bootstrap admin credential
- `invoice-ai/erpnext-frappe-secret-key`
  - persistent value written to the site `encryption_key` in `site_config.json`

### 3. Optional Future Secrets

Likely follow-up keys once the embedded stack exists:

- `invoice-ai/erpnext-encryption-key`
- `invoice-ai/erpnext-mail-config`
- `invoice-ai/erpnext-backup-target`
- `invoice-ai/docling-auth`

Do not create these until the module actually consumes them.

## Ownership Model

The host should populate secrets through `sops`.

The module should define:

- exact key names
- file formats
- file ownership
- restart relationships

The docs should not assume manual editing inside containers or mutable runtime bootstrap state for secrets.

## Minimal Population Workflow

1. Add the required keys to the host `sops` file.
2. Rebuild the NAS config so the secret files materialize with the expected owner/group.
3. Let the module:
   - write `/run/invoice-ai-erpnext/mariadb.env` from `invoice-ai/erpnext-db-root-password`
   - run the bench configurator job
   - create the default site with the admin password and site DB password
   - apply the persistent site `encryption_key` and optional `host_name`
4. Log into ERPNext as `Administrator`, create the dedicated `invoice-ai` service user, generate its API key/secret, and update `invoice-ai.erpnext-credentials`.
5. Rebuild or restart `invoice-ai.service` so the control plane starts using the durable ERPNext API credential pair.

## Current Minimum Set

For the current external-ERP configuration, the minimum set remains:

- `invoice-ai.env`
- `invoice-ai.operator-tokens`
- `invoice-ai.erpnext-credentials`

For the target embedded-ERP configuration, add:

- `invoice-ai/erpnext-db-root-password`
- `invoice-ai/erpnext-db-password`
- `invoice-ai/erpnext-admin-password`
- `invoice-ai/erpnext-frappe-secret-key`

## Minimal `server.yaml` Snippet

```yaml
invoice-ai:
  env: |
    INVOICE_AI_OLLAMA_URL=http://127.0.0.1:11434

  operator-tokens: |
    {
      "operators": [
        {
          "operator_id": "beau",
          "token": "replace-with-a-long-random-token"
        }
      ]
    }

  erpnext-credentials: |
    {
      "api_key": "replace-after-service-user-bootstrap",
      "api_secret": "replace-after-service-user-bootstrap"
    }

  erpnext-db-root-password: "replace-with-db-root-password"
  erpnext-db-password: "replace-with-site-db-password"
  erpnext-admin-password: "replace-with-erpnext-admin-password"
  erpnext-frappe-secret-key: "replace-with-fernet-style-encryption-key"
```

`erpnext-frappe-secret-key` should be a stable key suitable for Frappe's `encryption_key`. A practical way to generate one is:

```bash
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```
