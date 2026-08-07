from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.email.service import EmailAssistantService
from app.runtime.generation import (
    selected_generation_model,
    selected_generation_provider,
)
from app.settings import settings
from hansdb.conn import ensure_schema


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s - %(levelname)s - "
        "%(name)s - %(message)s"
    ),
)

logger = logging.getLogger(__name__)


database_connection: psycopg.Connection | None = None
email_service: EmailAssistantService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global database_connection
    global email_service

    logger.info("Starting enhanced HANS email API")

    database_connection = psycopg.connect(
        settings.database_url,
        autocommit=True,
    )

    ensure_schema(
        database_connection,
        required_version=1,
    )

    email_service = EmailAssistantService(
        database_connection
    )

    yield

    if database_connection is not None:
        database_connection.close()

    logger.info("Enhanced HANS email API stopped")


app = FastAPI(
    title="HANS Enhanced Email Assistant",
    description=(
        "GDPR-oriented, staff-facing email drafting service "
        "for HTW Berlin"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url=(
        "/docs"
        if settings.environment == "development"
        else None
    ),
    redoc_url=None,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://localhost",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=[
        "Content-Type",
        "X-HANS-API-Key",
    ],
)


class EmailRequest(BaseModel):
    email_text: str = Field(
        min_length=1,
        max_length=settings.max_email_characters,
    )
    student_email: Optional[str] = None
    subject: Optional[str] = None
    thread_id: Optional[str] = None
    email_id: Optional[str] = None
    language: Optional[str] = None
    top_k: int = Field(default=6, ge=3, le=10)


class SourceResponse(BaseModel):
    id: str
    title: str
    url: str
    type: str
    last_updated: str
    excerpt: str


class EmailResponse(BaseModel):
    is_followup: bool
    followup_type: str
    flagged_for_human: bool
    thread_id: str
    email_id: Optional[str]
    email_context: Dict[str, Any]
    detected_topics: List[Dict[str, Any]]
    staff_draft: str
    citations: List[str]
    sources: List[SourceResponse]
    validation: Dict[str, Any]
    quality: Dict[str, Any]
    conflicts: List[Dict[str, Any]]
    timing: Dict[str, float]
    automatic_send: bool


async def verify_internal_api_key(
    x_hans_api_key: str = Header(
        default="",
        alias="X-HANS-API-Key",
    ),
) -> None:
    configured_key = settings.api_key

    if not configured_key:
        raise HTTPException(
            status_code=503,
            detail="Internal API authentication is not configured",
        )

    if not secrets.compare_digest(
        x_hans_api_key,
        configured_key,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid internal API key",
        )


@app.get("/health")
async def health() -> Dict[str, Any]:
    database_ok = False

    if database_connection is not None:
        try:
            with database_connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                database_ok = cursor.fetchone()[0] == 1
        except Exception:
            logger.exception("Database health check failed")

    status = "healthy" if database_ok else "unhealthy"

    return {
        "status": status,
        "service": "hans-enhanced-email-assistant",
        "environment": settings.environment,
        "generation_provider": selected_generation_provider(),
        "generation_model": selected_generation_model(),
        "embedding_model": settings.embedding_model,
        "database": (
            "operational"
            if database_ok
            else "unavailable"
        ),
        "automatic_send": False,
    }


@app.post(
    "/email",
    response_model=EmailResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
@app.post(
    "/v1/drafts",
    response_model=EmailResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def process_email(
    request: EmailRequest,
) -> Dict[str, Any]:
    if email_service is None:
        raise HTTPException(
            status_code=503,
            detail="Email service is not initialized",
        )

    try:
        return await email_service.process_email(
            email_text=request.email_text.strip(),
            student_email=request.student_email,
            subject=request.subject,
            thread_id=request.thread_id,
            email_id=request.email_id,
            language=request.language,
            top_k=request.top_k,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Email processing failed")

        raise HTTPException(
            status_code=500,
            detail=(
                "HANS could not generate the staff draft. "
                "The email must be reviewed manually."
            ),
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "enhanced_api_server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=(
            settings.environment == "development"
        ),
    )