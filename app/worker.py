"""Async background task worker using ARQ and Redis for heavy ingestion and OCR."""

import logging
from urllib.parse import urlparse

from arq.connections import RedisSettings

from app.config import get_settings
from app.ingestion.normalizer import LLMClient, ingest_rows
from app.ingestion.parser import parse_file

logger = logging.getLogger("worker")


async def process_catalog_file(ctx: dict, file_path: str, source_label: str, clinic_code: str) -> dict:
    """Async background job to parse file (PDF/Excel/OCR) and normalize rows with LLM."""
    logger.info("Starting async background parsing for: %s (clinic: %s)", file_path, clinic_code)
    try:
        raw_rows = parse_file(file_path)
        settings = get_settings()
        llm = LLMClient()
        result = ingest_rows(
            raw_rows=raw_rows,
            llm=llm,
            threshold=settings.confidence_threshold,
            source_label=source_label,
            clinic_code=clinic_code,
        )
        logger.info("Async ingestion completed: %s rows ingested", result.get("ingested_count"))
        return result
    except Exception as exc:
        logger.exception("Failed async ingestion job: %s", exc)
        raise exc


def get_redis_settings() -> RedisSettings:
    settings = get_settings()
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "redis",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )


class WorkerSettings:
    functions = [process_catalog_file]
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 600  # 10 minutes max for large OCR/catalog files
