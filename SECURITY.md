# Security Policy

## Scope

This repository is a synthetic showcase. It is not clinical software, a medical device, or a production healthcare system. Do not use it with real patient, clinic, supplier-price, or operational data without a separate compliance review.

## Security Controls in the Demo

- Synthetic-only data in `sample_data/`.
- `X-API-Key` middleware on ingestion, agent, client-request, and review endpoints.
- `X-API-Key` is a demo-level shared secret, not user identity or role-based authorization.
- Demo images are pinned: Chroma `1.5.10.dev326` and n8n `1.123.100`.
- Pydantic v2 strict validation with `extra="forbid"`.
- Clinic isolation: `Product.clinic_code`, Chroma metadata filters, and SQL filters.
- Advanced retrieval isolation: `MultiVectorDocument.clinic_code` and `VisualPage.clinic_code` filters.
- Action allowlist: the planner returns a validated `ActionPlan`; unknown actions are rejected.
- Sentence Transformers v6.0 dependency is pinned; model names are fixed in configuration.
- Visual retrieval uses synthetic PDF pages only; no real patient or clinic pages are included.
- `search_product_visual` matches escalate to human review because page matches are not stock-verified products.
- Language fallback: only `en`, `es`, and `de` are supported; unknown languages escalate.
- PII masking and heuristic prompt-injection escalation.
- Low-confidence catalog rows staged in a human review queue.
- PostgreSQL and ChromaDB are not published to the host.
- API, n8n, and UI bind to `127.0.0.1` for local use.
- API and UI containers run as non-root `appuser`.
- `MAX_UPLOAD_MB` and `MAX_ROWS` limit ingestion abuse.
- `.env` is ignored; `.env.example` contains demo values only.

## Production Requirements

Before any real deployment, add real authentication and authorization, rate limiting, HTTPS/TLS, secrets management, network segmentation, dependency pinning, audit review, retention rules, and legal/compliance review. Replace the demo image tags with approved production releases. Pin Sentence Transformers and model revisions, use a dedicated multi-vector store rather than the PostgreSQL demo store, and validate visual-page handling against real privacy requirements. Validate any new language set and action allowlist before expanding the agent. The prompt-injection and PII checks are heuristic and are not a complete security boundary.

## Reporting

If you find a security issue in this showcase, report it through the repository's issue tracker. Do not include real sensitive data in reports or examples.
