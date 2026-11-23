import os

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000").rstrip("/")
API_KEY = os.getenv("INTERNAL_API_KEY", "demo-internal-api-key")

st.set_page_config(page_title="MedSupplyFlow-AI Admin UI", layout="wide")
st.title("MedSupplyFlow-AI Admin UI")

st.caption(
    "Synthetic demo data only. No real clinic names, supplier price lists, "
    "or patient data are included."
)

clinic_code = st.selectbox(
    "Demo clinic",
    ["demo-clinic-a", "demo-clinic-b", "demo-clinic-c"],
)

uploaded = st.file_uploader(
    "Upload a messy legacy catalog (.csv, .xlsx, .txt, or .pdf)",
    type=["csv", "xlsx", "txt", "pdf"],
)

if uploaded is not None:
    response = requests.post(
        f"{API_BASE_URL}/ingest",
        headers={"X-API-Key": API_KEY},
        files={
            "file": (uploaded.name, uploaded.getvalue(), "application/octet-stream")
        },
        data={
            "source_label": uploaded.name,
            "clinic_code": clinic_code,
        },
        timeout=90,
    )
    if response.ok:
        st.success("Ingestion completed")
        st.json(response.json())
    else:
        st.error(f"Ingestion failed: {response.status_code} {response.text}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Review Queue")
    response = requests.get(
        f"{API_BASE_URL}/review/queue",
        headers={"X-API-Key": API_KEY},
        timeout=30,
    )
    if response.ok:
        queue = response.json()
        if not queue:
            st.info("No products currently need review.")
        for item in queue:
            st.write(
                f"#{item['id']} | {item['sku']} | {item['clinic_code']} "
                f"| {item['canonical_name']} "
                f"| confidence {item['confidence_score']:.2f}"
            )

with col2:
    st.subheader("Client Requests")
    response = requests.get(
        f"{API_BASE_URL}/client/requests",
        headers={"X-API-Key": API_KEY},
        timeout=30,
    )
    if response.ok:
        st.json(response.json())

st.subheader("Human Review Actions")
product_id = st.number_input("Product ID", min_value=1, step=1)
action = st.selectbox("Action", ["approve", "reject"])
if st.button("Submit"):
    response = requests.post(
        f"{API_BASE_URL}/review/{int(product_id)}/{action}",
        headers={"X-API-Key": API_KEY},
        timeout=30,
    )
    st.json(response.json() if response.ok else {"error": response.text})
