CREATE TABLE IF NOT EXISTS clinics (
    id SERIAL PRIMARY KEY,
    clinic_code VARCHAR(40) NOT NULL UNIQUE,
    canonical_name VARCHAR(120) NOT NULL,
    region VARCHAR(60) NOT NULL DEFAULT 'demo-region'
);

INSERT INTO clinics (clinic_code, canonical_name, region)
VALUES
    ('demo-clinic-a', 'Demo Clinic A', 'demo-region'),
    ('demo-clinic-b', 'Demo Clinic B', 'demo-region'),
    ('demo-clinic-c', 'Demo Clinic C', 'demo-region')
ON CONFLICT (clinic_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(80) NOT NULL,
    canonical_name VARCHAR(180) NOT NULL,
    category VARCHAR(80) NOT NULL,
    sterile_type VARCHAR(40) NOT NULL DEFAULT 'sterile',
    unit_of_measure VARCHAR(30) NOT NULL,
    package_qty INTEGER NOT NULL DEFAULT 1,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    status VARCHAR(20) NOT NULL DEFAULT 'needs_review',
    clinic_code VARCHAR(40) NOT NULL DEFAULT 'demo-clinic-a'
        REFERENCES clinics(clinic_code),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (clinic_code, sku)
);

CREATE INDEX IF NOT EXISTS products_clinic_status_idx
    ON products (clinic_code, status);
CREATE INDEX IF NOT EXISTS products_sku_idx
    ON products (sku);

CREATE TABLE IF NOT EXISTS client_requests (
    id SERIAL PRIMARY KEY,
    client_name VARCHAR(100) NOT NULL,
    clinic_name VARCHAR(100) NOT NULL,
    clinic_code VARCHAR(40) NOT NULL DEFAULT 'demo-clinic-a'
        REFERENCES clinics(clinic_code),
    request_text TEXT NOT NULL,
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL DEFAULT 0,
    requested_by_date DATE,
    needs_human BOOLEAN NOT NULL DEFAULT FALSE,
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS client_requests_clinic_created_idx
    ON client_requests (clinic_code, created_at);
CREATE INDEX IF NOT EXISTS client_requests_product_idx
    ON client_requests (product_id);

CREATE TABLE IF NOT EXISTS ingestion_audit_logs (
    id SERIAL PRIMARY KEY,
    clinic_code VARCHAR(40) NOT NULL DEFAULT 'demo-clinic-a',
    source_label VARCHAR(200) NOT NULL DEFAULT 'legacy-catalog',
    raw_row TEXT NOT NULL,
    action VARCHAR(40) NOT NULL DEFAULT 'rejected',
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    details TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ingestion_audit_logs_clinic_idx
    ON ingestion_audit_logs (clinic_code);

CREATE TABLE IF NOT EXISTS multi_vector_documents (
    id SERIAL PRIMARY KEY,
    clinic_code VARCHAR(40) NOT NULL REFERENCES clinics(clinic_code),
    product_id INTEGER REFERENCES products(id),
    source_label VARCHAR(200) NOT NULL DEFAULT 'legacy-catalog',
    document_label VARCHAR(200) NOT NULL,
    document_text TEXT NOT NULL,
    token_vectors JSON NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS multi_vector_documents_clinic_idx
    ON multi_vector_documents (clinic_code);
CREATE INDEX IF NOT EXISTS multi_vector_documents_product_idx
    ON multi_vector_documents (product_id);

CREATE TABLE IF NOT EXISTS visual_pages (
    id SERIAL PRIMARY KEY,
    clinic_code VARCHAR(40) NOT NULL REFERENCES clinics(clinic_code),
    product_id INTEGER REFERENCES products(id),
    source_label VARCHAR(200) NOT NULL DEFAULT 'visual-catalog',
    page_number INTEGER NOT NULL,
    image BYTEA NOT NULL,
    token_vectors JSON NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS visual_pages_clinic_idx
    ON visual_pages (clinic_code);
CREATE INDEX IF NOT EXISTS visual_pages_clinic_page_idx
    ON visual_pages (clinic_code, page_number);
