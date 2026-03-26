# Dev Testing

`invoice-ai` does not yet ship a one-command disposable dependency stack.

The fastest current local loop is:

1. run the control plane against a temporary state directory
2. seed a local operator token file
3. point `INVOICE_AI_ERPNEXT_URL` at a mock ERP HTTP server
4. optionally point `INVOICE_AI_DOCLING_URL` at a mock Docling service
5. hit the FastAPI surface with fake data

## Minimal Operator Auth

Create a temporary token file:

```bash
tmp="$(mktemp -d)"
cat >"$tmp/operators.json" <<'EOF'
{
  "operators": [
    { "operator_id": "local-dev", "token": "dev-token" }
  ]
}
EOF
```

## Temporary Runtime

Run the service with local-only state:

```bash
export INVOICE_AI_STATE_DIR="$tmp/state"
export INVOICE_AI_OPERATOR_TOKENS_FILE="$tmp/operators.json"
export INVOICE_AI_ERPNEXT_URL="http://127.0.0.1:9999"
nix run . -- serve-http
```

The dummy `INVOICE_AI_ERPNEXT_URL` is currently needed even for review-only planner/orchestrator flows because executor construction is still broader than it should be. That is tracked as follow-up issue `coordinator-2xm`.

## Fastest Smoke Test

Confirm the authenticated operator API is up:

```bash
curl -s \
  -H 'Authorization: Bearer dev-token' \
  http://127.0.0.1:4310/api/runtime
```

Run a planner or tool request:

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
- mock ERP and Docling endpoints by configuration

What does not exist yet:

- a checked-in disposable ERPNext fixture
- a checked-in disposable Docling fixture
- a one-command end-to-end dev stack
- broad integration tests over that stack

That missing disposable stack belongs in the deployment and verification lane, not in the current control-plane runtime itself.
