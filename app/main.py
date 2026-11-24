import hmac
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .agent.graph import run_request
from .config import get_settings
from .db.models import ClientRequest, Product
from .db.multi_vector_store import delete_product_document, get_multi_vector_store
from .db.session import SessionLocal, init_db
from .db.vector_store import VectorStore
from .ingestion.normalizer import LLMClient, ingest_rows
from .ingestion.parser import parse_file
from .ingestion.schemas import ClinicCode, RequestInput
from .ingestion.visual_parser import store_visual_pages

PROTECTED_PREFIXES = ("/ingest", "/agent/request", "/client/requests", "/review/")


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="MedSupplyFlow-AI",
    description="Synthetic surgical catalog ingestion + LangGraph request agent",
    lifespan=lifespan,
)


@app.middleware("http")
async def api_key_middleware(request, call_next):
    if request.url.path.startswith(PROTECTED_PREFIXES):
        supplied = request.headers.get("X-API-Key")
        expected = get_settings().internal_api_key
        if not supplied or not hmac.compare_digest(supplied, expected):
            return JSONResponse(
                status_code=401,
                content={"detail": "missing or invalid X-API-Key"},
            )
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok", "service": "medsupplyflow-ai"}


@app.post("/ingest")
def ingest(
    file: UploadFile = File(...),
    source_label: str = "synthetic legacy catalog",
    clinic_code: ClinicCode = "demo-clinic-a",
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename is required")
    if len(source_label) > 200:
        raise HTTPException(status_code=400, detail="source_label is too long")

    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"upload exceeds {settings.max_upload_mb} MB",
        )

    suffix = Path(file.filename).suffix.lower()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        raw_rows = parse_file(tmp_path)
        if len(raw_rows) > settings.max_rows:
            raise HTTPException(
                status_code=400,
                detail=f"catalog exceeds {settings.max_rows} rows",
            )
        summary = ingest_rows(
            raw_rows=raw_rows,
            llm=LLMClient(),
            threshold=settings.confidence_threshold,
            source_label=source_label,
            clinic_code=clinic_code,
        )
        return {
            "source": file.filename,
            "clinic_code": clinic_code,
            "rows_parsed": len(raw_rows),
            "summary": summary,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/ingest/visual")
def ingest_visual(
    file: UploadFile = File(...),
    source_label: str = "synthetic visual catalog",
    clinic_code: ClinicCode = "demo-clinic-a",
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename is required")
    if len(source_label) > 200:
        raise HTTPException(status_code=400, detail="source_label is too long")
    if Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="visual ingestion requires a PDF")

    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"upload exceeds {settings.max_upload_mb} MB",
        )

    try:
        pages_stored = store_visual_pages(
            data=content,
            clinic_code=clinic_code,
            source_label=source_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="visual ingestion failed") from exc

    return {
        "source": file.filename,
        "clinic_code": clinic_code,
        "pages_stored": pages_stored,
    }


@app.post("/agent/request")
def agent_request(payload: RequestInput):
    return run_request(
        client_name=payload.client_name,
        clinic_name=payload.clinic_name,
        clinic_code=payload.clinic_code,
        request_text=payload.request_text,
    )


@app.get("/client/requests")
def client_requests(session: Session = Depends(get_db)):
    requests = session.execute(
        select(ClientRequest).order_by(ClientRequest.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": request.id,
            "client_name": request.client_name,
            "clinic_name": request.clinic_name,
            "clinic_code": request.clinic_code,
            "request_text": request.request_text,
            "product_id": request.product_id,
            "sku": request.product.sku if request.product else None,
            "quantity": request.quantity,
            "requested_by_date": (
                request.requested_by_date.isoformat()
                if request.requested_by_date
                else None
            ),
            "needs_human": request.needs_human,
            "confidence_score": request.confidence_score,
        }
        for request in requests
    ]


@app.get("/review/queue")
def review_queue(session: Session = Depends(get_db)):
    products = session.execute(
        select(Product).where(Product.status == "needs_review")
    ).scalars().all()
    return [
        {
            "id": product.id,
            "sku": product.sku,
            "clinic_code": product.clinic_code,
            "canonical_name": product.canonical_name,
            "confidence_score": product.confidence_score,
            "status": product.status,
        }
        for product in products
    ]


@app.post("/review/{product_id}/approve")
def approve_product(product_id: int, session: Session = Depends(get_db)):
    product = session.execute(
        select(Product).where(Product.id == product_id)
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")

    product.status = "approved"
    product.confidence_score = max(product.confidence_score, 1.0)
    session.commit()
    VectorStore().index_product(product)
    multi_vector_indexed = False
    try:
        get_multi_vector_store().store_product_document(product)
        multi_vector_indexed = True
    except Exception:
        pass
    return {
        "id": product.id,
        "sku": product.sku,
        "clinic_code": product.clinic_code,
        "status": product.status,
        "multi_vector_indexed": multi_vector_indexed,
    }


@app.post("/review/{product_id}/reject")
def reject_product(product_id: int, session: Session = Depends(get_db)):
    product = session.execute(
        select(Product).where(Product.id == product_id)
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")

    product.status = "rejected"
    product.notes = (product.notes + " | rejected by human reviewer").strip()
    session.commit()
    delete_product_document(product.id, product.clinic_code)
    return {
        "id": product.id,
        "sku": product.sku,
        "clinic_code": product.clinic_code,
        "status": product.status,
    }
