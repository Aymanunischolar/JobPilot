"""JobPilot API routes.

Thin HTTP layer over the Manager Agent graph (§4.1). Every endpoint here
maps directly to a step in the architecture doc's routing table: upload
kicks off search → score → tailor → QA and pauses at the Human Approval
Gate; the approval endpoint is the only way to move a posting past that
gate into the Application Agent (§6.1).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.agents.manager import get_state_snapshot, record_approval, resume_after_approval, run_pipeline
from app.core.config import get_settings
from app.core.tracing import load_trace
from app.schemas.models import ApprovalDecision, Channel, JobState

logger = logging.getLogger("jobpilot")

router = APIRouter()

_MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10MB — generous for a resume, cheap to enforce

# Generous but bounded: a cold-started free-tier instance plus a full
# search -> score -> tailor -> faithfulness run for ~15 postings should
# comfortably finish well under this. Past it, something is genuinely
# stuck (not just slow), so failing predictably with a 504 beats leaving
# the client hanging until the platform kills the connection on its own.
_PIPELINE_TIMEOUT_SECONDS = 110
_APPROVAL_TIMEOUT_SECONDS = 60


class ApprovalRequest(BaseModel):
    posting_id: str
    decision: ApprovalDecision
    approved_by: str | None = None
    channel: Channel | None = None


@router.post("/resume/upload", response_model=JobState)
async def upload_resume(file: UploadFile = File(...)) -> JobState:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".doc"):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX resumes are supported")

    settings = get_settings()
    content = await file.read()
    if len(content) > _MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Resume file is too large (10MB limit)")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    session_id = uuid.uuid4().hex[:12]
    resumes_dir = settings.data_dir / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    resume_path = resumes_dir / f"{session_id}{suffix}"
    resume_path.write_bytes(content)

    try:
        return await asyncio.wait_for(
            run_pipeline(
                resume_bytes=content,
                resume_filename=file.filename,
                thread_id=session_id,
                resume_file_path=str(resume_path),
            ),
            timeout=_PIPELINE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        logger.warning("Pipeline timed out for session=%s", session_id)
        raise HTTPException(
            status_code=504,
            detail=(
                f"Resume processing is taking longer than expected (session {session_id}). "
                "Try again — a subsequent run often lands on a warmer instance and faster LLM responses."
            ),
        ) from exc
    except RuntimeError as exc:
        # Missing/misconfigured provider keys (job_search.py, ats_scorer.py
        # LLM fallbacks) surface here as RuntimeError — a config problem,
        # not a bug, so it's worth a clearer status than a bare 500.
        logger.warning("Pipeline unavailable for session=%s: %s", session_id, exc)
        raise HTTPException(
            status_code=503,
            detail="A required search/LLM provider is unavailable right now. Please try again shortly.",
        ) from exc
    except Exception as exc:  # noqa: BLE001 — boundary: never leak internals to the client
        logger.exception("Pipeline failed for session=%s", session_id)
        raise HTTPException(
            status_code=500,
            detail=f"Resume processing failed (session {session_id}). Please try again.",
        ) from exc


@router.get("/sessions/{session_id}", response_model=JobState)
async def get_session(session_id: str) -> JobState:
    job_state = await get_state_snapshot(session_id)
    if job_state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return job_state


@router.post("/sessions/{session_id}/approvals", response_model=JobState)
async def submit_approval(session_id: str, body: ApprovalRequest) -> JobState:
    """Records a human decision on a specific posting (§6.1). Only an
    APPROVED decision moves that posting toward the Application Agent;
    REJECTED is recorded and the posting goes no further."""
    try:
        await record_approval(
            thread_id=session_id,
            posting_id=body.posting_id,
            decision=body.decision,
            approved_by=body.approved_by,
            channel=body.channel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        return await asyncio.wait_for(
            resume_after_approval(session_id), timeout=_APPROVAL_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError as exc:
        logger.warning("Resume-after-approval timed out for session=%s", session_id)
        raise HTTPException(
            status_code=504,
            detail=(
                f"Your approval was recorded, but applying it is taking longer than expected "
                f"(session {session_id}). Refresh the session to check status."
            ),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Resume-after-approval failed for session=%s", session_id)
        raise HTTPException(
            status_code=500,
            detail=(
                f"Your approval was recorded, but applying it failed (session {session_id}). "
                "Refresh the session to check status, or try again."
            ),
        ) from exc


@router.get("/trace/{trace_id}", response_model=JobState)
async def get_trace(trace_id: str) -> JobState:
    job_state = load_trace(trace_id)
    if job_state is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return job_state
