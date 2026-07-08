"""Admin dashboard API — every resume upload, agent response, and
approval decision, for internal review. Protected by HTTP Basic Auth;
credentials come from ADMIN_USERNAME/ADMIN_PASSWORD (defaults: admin /
123456 — change these before deploying anywhere reachable by others).
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core import admin_store
from app.core.config import get_settings
from app.schemas.models import JobState

router = APIRouter()
_security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(_security)) -> str:
    settings = get_settings()
    valid_user = secrets.compare_digest(credentials.username, settings.admin_username)
    valid_pass = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (valid_user and valid_pass):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@router.get("/runs")
async def list_runs(_: str = Depends(require_admin)) -> list[dict]:
    """Summary list for the dashboard table — every resume run, most
    recently updated first."""
    return admin_store.list_runs()


@router.get("/runs/{session_id}", response_model=JobState)
async def get_run(session_id: str, _: str = Depends(require_admin)) -> JobState:
    """Full detail for one run: parsed resume, postings, ATS responses,
    tailored output, approvals, and the full agent decision trace."""
    job_state = admin_store.get_run(session_id)
    if job_state is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return job_state
