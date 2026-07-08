"""JobPilot API routes.

Thin HTTP layer over the Manager Agent graph (§4.1). Every endpoint here
maps directly to a step in the architecture doc's routing table: upload
kicks off search → score → tailor → QA and pauses at the Human Approval
Gate; the approval endpoint is the only way to move a posting past that
gate into the Application Agent (§6.1).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.agents.manager import get_state_snapshot, record_approval, resume_after_approval, run_pipeline
from app.core.config import get_settings
from app.core.tracing import load_trace
from app.schemas.models import ApprovalDecision, Channel, JobState

router = APIRouter()


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

    session_id = uuid.uuid4().hex[:12]
    resumes_dir = settings.data_dir / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    resume_path = resumes_dir / f"{session_id}{suffix}"
    resume_path.write_bytes(content)

    try:
        job_state = await run_pipeline(
            resume_bytes=content,
            resume_filename=file.filename,
            thread_id=session_id,
            resume_file_path=str(resume_path),
        )
    except Exception as exc:  # noqa: BLE001 — surfaced to the client as a 500 with context
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}") from exc

    return job_state


@router.get("/sessions/{session_id}", response_model=JobState)
async def get_session(session_id: str) -> JobState:
    job_state = get_state_snapshot(session_id)
    if job_state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return job_state


@router.post("/sessions/{session_id}/approvals", response_model=JobState)
async def submit_approval(session_id: str, body: ApprovalRequest) -> JobState:
    """Records a human decision on a specific posting (§6.1). Only an
    APPROVED decision moves that posting toward the Application Agent;
    REJECTED is recorded and the posting goes no further."""
    try:
        record_approval(
            thread_id=session_id,
            posting_id=body.posting_id,
            decision=body.decision,
            approved_by=body.approved_by,
            channel=body.channel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    job_state = await resume_after_approval(session_id)
    return job_state


@router.get("/trace/{trace_id}", response_model=JobState)
async def get_trace(trace_id: str) -> JobState:
    job_state = load_trace(trace_id)
    if job_state is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return job_state
