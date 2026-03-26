# Dev Testing

`invoice-ai` now ships a one-command disposable mock-backed dependency stack for local end-to-end testing.

The fastest local loops are:

1. `nix run . -- dev-stack`
2. `nix run . -- dev-smoke-test`

## Disposable Dev Stack

Run:

```bash
nix run . -- dev-stack
```

This starts:

- a disposable `invoice-ai` FastAPI service
- a seeded mock ERPNext HTTP backend
- a seeded mock Docling HTTP backend
- a temp runtime state tree
- a temp operator token file

The command prints JSON that includes:

- `service_url`
- `operator_token`
- `operators_file`
- `state_dir`
- `sample_supplier_invoice_pdf`

Leave it running, then in another shell:

```bash
curl -s \
  -H 'Authorization: Bearer dev-token' \
  http://127.0.0.1:4310/api/runtime
```

You can then drive planner/orchestrator flows over HTTP with fake data.

## One-Command Smoke Test

Run:

```bash
nix run . -- dev-smoke-test
```

This verifies the current mock-backed end-to-end path:

- authenticated operator API startup
- quote drafting
- quote-to-invoice draft conversion
- supplier document intake through extraction, normalization, and draft purchase-invoice creation

The command returns a JSON summary including the generated ERP refs and temp-state paths.

## Manual Review-Only CLI Loop

The CLI path now auto-initializes the runtime store. A blank temp state directory is enough even for review-only planner/orchestrator turns:

```bash
tmp="$(mktemp -d)"
cat >"$tmp/request.json" <<'EOF'
{
  "request_id": "review-turn-1",
  "tool_name": "planner.handle_turn",
  "payload": {
    "message": "show pending reviews"
  }
}
EOF

INVOICE_AI_STATE_DIR="$tmp/state" \
  nix run . -- run-tool --request-file "$tmp/request.json"
```

`INVOICE_AI_ERPNEXT_URL` is no longer required for that review-only path.

## Manual HTTP Quote Request

If you prefer to drive a specific operator turn manually against the dev stack:

```bash
curl -s \
  -H 'Authorization: Bearer dev-token' \
  -H 'Content-Type: application/json' \
  -X POST http://127.0.0.1:4310/api/tools/run \
  -d '{
    "request_id": "dev-quote-1",
    "tool_name": "planner.handle_turn",
    "payload": {
      "message": "Quote Acme for 2 hours onsite labour"
    },
    "conversation_context": {
      "defaults": {
        "quote": {
          "company": "Test Company",
          "customer": "CUST-ACME",
          "customer_name": "Acme",
          "currency": "AUD",
          "labor_item_code": "LABOUR"
        }
      }
    }
  }'
```

## Current Fake-Data Story

What exists today:

- blank local control-plane state
- local bearer-token auth
- fake quote/invoice/supplier inputs
- checked-in disposable mock ERP and Docling endpoints
- one-command local smoke verification

What does not exist yet:

- a disposable real ERPNext fixture
- a Nix-owned dependency stack that runs real ERPNext and Docling together
- broad integration tests over a real dependency environment

The remaining e2e work belongs in the deployment and verification lane:

- integrate the module into `nix-dotfiles`
- add retention and cleanup behavior for the runtime tree
- prove the operator path against a more realistic ERPNext dependency
