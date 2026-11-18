from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.email.service import EmailAssistantService
from app.mailbox.factory import (
    build_mailbox_client,
    build_mailbox_writer,
    mailbox_enabled,
    mailbox_send_enabled,
    mailbox_write_enabled,
)
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


class MailboxWriteRequest(BaseModel):
    to_email: str = Field(min_length=3, max_length=320)
    subject: str = Field(default="", max_length=500)
    body: str = Field(min_length=1, max_length=settings.max_email_characters)
    in_reply_to: Optional[str] = None


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
    observability: Dict[str, Any] = Field(
        default_factory=dict
    )
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


@app.get(
    "/mailbox/status",
    dependencies=[Depends(verify_internal_api_key)],
)
async def mailbox_status() -> Dict[str, Any]:
    """Report mailbox capabilities exposed to the staff UI."""
    return {
        "enabled": mailbox_enabled(),
        "write_enabled": mailbox_write_enabled(),
        "send_enabled": mailbox_send_enabled(),
        "automatic_send": False,
        "read_only": not mailbox_write_enabled(),
    }


@app.get(
    "/mailbox/messages",
    dependencies=[Depends(verify_internal_api_key)],
)
async def mailbox_messages(
    limit: int = 20,
    unread_only: bool = True,
) -> Dict[str, Any]:
    """
    Return normalized incoming mailbox messages for the staff UI.

    Mailbox access is read-only. Fetching messages does not call the HANS
    generation pipeline and therefore consumes no model tokens.
    """
    if not mailbox_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Mailbox integration is disabled. "
                "Set HANS_MAILBOX_ENABLED=true to enable it."
            ),
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Mailbox message limit must be between 1 and 100.",
        )

    try:
        client = build_mailbox_client()

        messages = await run_in_threadpool(
            client.list_messages,
            limit=limit,
            unread_only=unread_only,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception(
            "Mailbox message retrieval failed"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "HANS could not read the configured mailbox. "
                "Check mailbox configuration and connectivity."
            ),
        ) from exc

    return {
        "count": len(messages),
        "unread_only": unread_only,
        "messages": [
            message.to_dict()
            for message in messages
        ],
        "automatic_send": False,
        "read_only": True,
    }


@app.post(
    "/mailbox/drafts",
    dependencies=[Depends(verify_internal_api_key)],
)
async def mailbox_save_draft(
    request: MailboxWriteRequest,
) -> Dict[str, Any]:
    """Save a staff-reviewed reply to the configured mailbox Drafts folder."""
    if not mailbox_write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Mailbox draft writing is disabled. "
                "Set HANS_MAILBOX_WRITE_ENABLED=true to enable it."
            ),
        )

    try:
        writer = build_mailbox_writer()
        message_id = await run_in_threadpool(
            writer.save_draft,
            to_email=request.to_email.strip(),
            subject=request.subject.strip(),
            body=request.body.strip(),
            in_reply_to=(
                request.in_reply_to.strip()
                if request.in_reply_to
                else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Mailbox draft creation failed")
        raise HTTPException(
            status_code=502,
            detail=(
                "HANS could not save the message to the configured "
                "mailbox Drafts folder."
            ),
        ) from exc

    return {
        "status": "saved",
        "message_id": message_id,
        "automatic_send": False,
    }


@app.post(
    "/mailbox/send",
    dependencies=[Depends(verify_internal_api_key)],
)
async def mailbox_send(
    request: MailboxWriteRequest,
) -> Dict[str, Any]:
    """Send one message only after an explicit staff action in the UI."""
    if not mailbox_send_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Mailbox sending is disabled. "
                "Set HANS_MAILBOX_SEND_ENABLED=true to enable it."
            ),
        )

    try:
        writer = build_mailbox_writer()
        message_id = await run_in_threadpool(
            writer.send_message,
            to_email=request.to_email.strip(),
            subject=request.subject.strip(),
            body=request.body.strip(),
            in_reply_to=(
                request.in_reply_to.strip()
                if request.in_reply_to
                else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Mailbox send failed")
        raise HTTPException(
            status_code=502,
            detail=(
                "HANS could not send the message through the "
                "configured mailbox provider."
            ),
        ) from exc

    return {
        "status": "sent",
        "message_id": message_id,
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