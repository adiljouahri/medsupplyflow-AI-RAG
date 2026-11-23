# MedSupplyFlow-AI Architecture

## High-Level System

```mermaid
flowchart TB
    subgraph Clients
        CLIENT["Client request / WhatsApp / email"]
        LEGACY["Legacy catalog files: CSV, XLSX, TXT, PDF"]
        VISUAL["Synthetic PDF page images"]
    end

    subgraph Docker
        N8N["n8n orchestrator: webhooks, retries, alerts"]
        API["FastAPI + LangGraph: guardrails, language, planner, executor"]
        PG[("PostgreSQL: products, stock, requests, audit logs, multi-vector docs, visual pages")]
        CH[("ChromaDB: dense product embeddings")]
        UI["Streamlit: ingestion and review queue"]
    end

    LEGACY --> API
    VISUAL --> API
    CLIENT --> N8N
    N8N --> API
    API --> PG
    API --> CH
    API --> N8N
    API <--> UI
```

## Request Agent Flow

```mermaid
flowchart LR
    REQUEST["Client request"]
    GUARDRAILS["Guardrails: PII masking + injection refusal"]
    LANGUAGE["Language detection: en / es / de"]
    PLANNER["Planner: strict ActionPlan JSON"]
    EXECUTOR["Executor: allowlisted actions"]

    REQUEST --> GUARDRAILS
    GUARDRAILS --> LANGUAGE
    LANGUAGE --> PLANNER
    PLANNER --> EXECUTOR
    EXECUTOR --> RESPONSE["Response / order / human escalation"]
```

## Retrieval and Verification

```mermaid
flowchart LR
    EXECUTOR["Executor"]
    HYBRID["Hybrid search: Chroma shortlist"]
    SQL["PostgreSQL verification: approved status + stock"]
    RESPONSE["Database-backed response or order"]

    EXECUTOR --> HYBRID
    HYBRID --> SQL
    SQL --> RESPONSE

    EXECUTOR --> MULTI["Multi-vector search: MaxSim over PostgreSQL"]
    MULTI --> CHECK["Product mapping + stock verification"]
    CHECK --> RESPONSE

    EXECUTOR --> VISUAL["Visual search: page-image MaxSim"]
    VISUAL --> HUMAN["Human review: visual pages are not stock-verified products"]
```

## Ingestion Flow

```mermaid
flowchart LR
    UPLOAD["Catalog upload"]
    PARSER["Parser: CSV / XLSX / TXT / PDF + OCR fallback"]
    NORMALIZER["Normalizer: strict Pydantic schema"]
    AUDIT["Ingestion audit log"]
    PRODUCTS["PostgreSQL products"]

    UPLOAD --> PARSER
    PARSER --> NORMALIZER
    NORMALIZER --> AUDIT
    NORMALIZER --> PRODUCTS

    APPROVED["Approved product"]
    APPROVED --> CHROMA["ChromaDB dense embedding"]
    APPROVED --> MULTI["PostgreSQL multi-vector document"]

    VISUAL_PDF["Synthetic PDF"]
    VISUAL_PDF --> VISUAL_PARSER["Page image rendering"]
    VISUAL_PARSER --> VISUAL_PAGES["PostgreSQL visual pages"]
```

## Trust Boundaries and Isolation

- `X-API-Key` middleware protects ingestion, agent, client-request, review, and visual ingestion endpoints.
- Clinic isolation is enforced by `clinic_code` in PostgreSQL, Chroma metadata filters, `MultiVectorDocument`, and `VisualPage`.
- The planner only returns allowlisted actions: `search_product`, `search_product_multi_vector`, `search_product_visual`, `check_stock`, `create_order`, `respond`, `ask_human`.
- The executor verifies product status and stock before creating an order.
- Visual page matches are explicitly escalated to human review because they are not automatically mapped to stock-verified products.
- Multi-vector and visual retrieval are optional advanced paths; Chroma remains the fast dense shortlist.
- PostgreSQL and ChromaDB are internal services; the API, n8n, and UI are localhost-bound in the demo.

## Full Architecture Diagram Source

The following Mermaid source generates `mermaid-diagram-full.png`:

```mermaid
flowchart TB
    %% 1. External Inputs
    subgraph EXT["External Clients & Files"]
        CLIENT["Client Request<br/>(WhatsApp / Email)"]
        LEGACY["Legacy Catalog Files<br/>(CSV, XLSX, TXT, PDF)"]
        SYNTH["Synthetic PDF<br/>(Catalog Pages)"]
    end

    %% 2. Docker Environment
    subgraph DOCKER["Docker Deployment (API, n8n & UI localhost-bound in demo; DBs internal)"]
        
        subgraph EDGE["Orchestration & Operator UI"]
            N8N["n8n Orchestrator<br/>Webhooks, retries, alerts"]
            UI["Streamlit UI<br/>Catalog ingestion & human review queue"]
        end

        %% 3. FastAPI + LangGraph Trust Boundary
        subgraph API_BOX["FastAPI + LangGraph (Trust Boundary)"]
            AUTH["X-API-Key Middleware<br/>Protects agent, ingestion, review & visual endpoints"]

            subgraph INGEST["Ingestion Pipeline"]
                ING_PARSE["Parser<br/>CSV / XLSX / TXT / PDF + OCR fallback"]
                ING_NORM["Normalizer<br/>Strict Pydantic schema"]
                ING_APPROVE["Approval Indexing<br/>Approved products only"]
                ING_VIS["Visual Page Renderer<br/>PDF to page images"]
            end

            subgraph AGENT["Request Agent Pipeline"]
                GUARD["Guardrails<br/>PII masking + injection refusal"]
                LANG["Language Detection<br/>en / es / de"]
                PLAN["Planner<br/>Strict ActionPlan JSON<br/>Allowlisted: search_product, search_product_multi_vector,<br/>search_product_visual, check_stock, create_order, respond, ask_human"]
                EXEC["Executor<br/>Runs allowlisted actions"]
            end

            subgraph VERIFY["Verification & Outcomes"]
                SQL_VER["PostgreSQL Verification<br/>Approved status + stock check"]
                RESP_OK["DB-Backed Response<br/>or Create Order"]
                ESC_HUM["Escalate to Human Review<br/>(ask_human / alerts)"]
            end
        end

        %% 4. Internal Data Stores
        subgraph STORES["Internal Data Stores (clinic_code Isolated)"]
            CH[("ChromaDB<br/>Dense product embeddings<br/>(clinic_code metadata filter)")]

            subgraph PG_GROUP["PostgreSQL (Isolated by clinic_code)"]
                PG_CORE[("Core Tables<br/>Products, Stock, Requests, Audit Logs")]
                PG_MV[("MultiVectorDocument<br/>(MaxSim vectors)")]
                PG_VIS[("VisualPage<br/>(Page-image MaxSim vectors)")]
            end
        end
    end

    %% External & UI Entry Flows
    CLIENT <--> N8N
    N8N -->|"Client request"| AUTH
    LEGACY -->|"Catalog upload"| AUTH
    SYNTH -->|"Visual upload"| AUTH
    UI <-->|"Ingestion & review actions"| AUTH

    %% Ingestion Flows
    AUTH --> ING_PARSE
    ING_PARSE --> ING_NORM
    ING_NORM -->|"Products + audit log"| PG_CORE
    UI -.->|"Approve product"| AUTH
    AUTH --> ING_APPROVE
    ING_APPROVE -->|"Dense embedding"| CH
    ING_APPROVE -->|"Multi-vector doc"| PG_MV
    AUTH --> ING_VIS
    ING_VIS -->|"Rendered pages"| PG_VIS

    %% Request Agent Flows
    AUTH --> GUARD
    GUARD --> LANG
    LANG --> PLAN
    PLAN --> EXEC

    %% Retrieval & Verification Paths
    EXEC -->|"1. Hybrid search (fast shortlist)"| CH
    CH --> SQL_VER

    EXEC -->|"2. Multi-vector MaxSim (optional)"| PG_MV
    PG_MV -->|"Product mapping"| SQL_VER

    SQL_VER <-->|"Verify status, stock & write order"| PG_CORE
    SQL_VER --> RESP_OK

    EXEC -->|"3. Visual page MaxSim (optional)"| PG_VIS
    PG_VIS -->|"Not stock-verified"| ESC_HUM
    EXEC -->|"ask_human"| ESC_HUM

    %% Outbound Responses & Alerts
    RESP_OK -->|"Response / order status"| N8N
    ESC_HUM -->|"Alerts"| N8N
    ESC_HUM -->|"Review queue"| UI

    %% Dashed Trust Boundary Styling
    style API_BOX stroke-dasharray: 5 5
    style STORES stroke-dasharray: 5 5
```
