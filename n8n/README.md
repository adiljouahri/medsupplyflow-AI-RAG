# n8n Workflows

These are starter exports for the synthetic demo stack.

## Import

1. Start the stack with `docker compose up -d` (only after you decide to run it).
2. Open n8n at `http://localhost:5678`.
3. Import `workflows/client_request_flow.json`, `workflows/whatsapp_request_flow.json`, `workflows/email_notification_flow.json`, and `workflows/error_handler_flow.json`.
4. Confirm the HTTP Request nodes point at `http://api:8000/agent/request`.
5. Replace the demo `X-API-Key` header with your local `.env` value.
6. Keep the synthetic clinic codes `demo-clinic-a`, `demo-clinic-b`, and `demo-clinic-c` in the payload.

The API key, clinic names, and request text in these JSONs are demo placeholders only.
The webhook payload is a hard-coded synthetic example. For a production webhook,
swap the JSON body for the incoming payload and keep the same API key header.

## Safety

- Human escalation happens when `needs_human` is true.
- The confirmation branch never invents products or prices; it returns only
  the database-backed order summary and detected language.
- Language detection happens in FastAPI, not in n8n.
- The email flow is a synthetic mock and does not send real emails.
- The error handler logs failed calls so client requests are not silently dropped.
