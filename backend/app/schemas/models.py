"""Typed data contracts shared across all JobPilot agents.

These are the Pydantic models referenced throughout the architecture
document (see docs/ARCHITECTURE.md §5). ``JobState`` is the single object
passed through LangGraph's state channel; every agent reads from and
writes to a scoped slice of it. Typed contracts are what make the
Manager's gating logic possible — a gate can only enforce a rule it can
actually read (§5).
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# --------------------------------------------------------------------------
# Resume Parser Agent output (§4.2)
# --------------------------------------------------------------------------


class Bullet(BaseModel):
    """A single, atomic achievement/responsibility line from a resume."""

    id: str = Field(default_factory=_new_id)
    text: str
    quantified_metrics: list[str] = Field(default_factory=list)


class RoleExperience(BaseModel):
    title: str
    company: str
    start_date: str | None = None
    end_date: str | None = None  # None / "present" = current role
    bullets: list[Bullet] = Field(default_factory=list)


class Education(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    graduation_date: str | None = None


class ParsedResume(BaseModel):
    """Output of the Resume Parser Agent — a typed schema derived from an
    unstructured PDF/DOCX resume (§4.2)."""

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    skills: list[str] = Field(default_factory=list)
    roles: list[RoleExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    raw_text_hash: str = ""  # for traceability checks (§5.2)

    def all_bullets(self) -> dict[str, Bullet]:
        """Every bullet across every role, keyed by its ID — the source of
        truth the faithfulness checker validates against (§6.2)."""
        return {b.id: b for role in self.roles for b in role.bullets}


# --------------------------------------------------------------------------
# Job Search Agent output (§4.3)
# --------------------------------------------------------------------------


class JobPosting(BaseModel):
    id: str = Field(default_factory=_new_id)
    source_url: str
    canonical_url: str
    jd_text: str
    jd_hash: str = ""  # near-duplicate JD hashing for dedup (§4.3)
    company: str
    title: str
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.0)


# --------------------------------------------------------------------------
# ATS Scorer Agent output (§4.4, weights table §7 stack)
# --------------------------------------------------------------------------


class ATSSignalBreakdown(BaseModel):
    keyword_coverage: float = 0.0  # weight 40%
    title_seniority_alignment: float = 0.0  # weight 20%
    experience_match: float = 0.0  # weight 15%
    education_match: float = 0.0  # weight 10%
    formatting_compatibility: float = 0.0  # weight 15%


class ATSResult(BaseModel):
    score: float = Field(ge=0.0, le=100.0)
    missing_keywords: list[str] = Field(default_factory=list)
    fit_rationale: str
    passed_gate: bool  # score >= ATS_PASS_THRESHOLD (default 70)
    signal_breakdown: ATSSignalBreakdown = Field(default_factory=ATSSignalBreakdown)


# --------------------------------------------------------------------------
# Tailor Agent output (§4.5)
# --------------------------------------------------------------------------


class TailoredBullet(BaseModel):
    source_bullet_id: str  # must exist in ParsedResume.all_bullets() (§5.2)
    text: str
    keywords_surfaced: list[str] = Field(default_factory=list)


class FaithfulnessStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED_STRUCTURAL = "failed_structural"
    FAILED_SEMANTIC = "failed_semantic"


class TailoredResume(BaseModel):
    bullets: list[TailoredBullet] = Field(default_factory=list)
    cover_letter: str = ""
    diff_summary: str = ""
    faithfulness_status: FaithfulnessStatus = FaithfulnessStatus.PENDING
    faithfulness_violations: list[str] = Field(default_factory=list)  # bullet ids/reasons


# --------------------------------------------------------------------------
# Human Approval Gate (§6.1)
# --------------------------------------------------------------------------


class Channel(str, Enum):
    """Allow-list categories from §6.3."""

    CAREER_PAGE_ALLOWLISTED = "career_page_allowlisted"  # auto-fill + auto-submit
    MAJOR_JOB_BOARD = "major_job_board"  # auto-fill only, human clicks submit
    EMAIL = "email"  # draft only, human sends


class ApprovalDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalStatus(BaseModel):
    decision: ApprovalDecision = ApprovalDecision.PENDING
    channel: Channel | None = None
    approved_by: str | None = None
    decided_at: datetime | None = None


# --------------------------------------------------------------------------
# Observability (§7.1)
# --------------------------------------------------------------------------


class TraceEvent(BaseModel):
    trace_id: str
    agent: str
    input_hash: str
    output_hash: str
    decision: str  # e.g. "pass", "reject", "escalate", "retry"
    rationale: str = ""
    latency_ms: float = 0.0
    timestamp: float = Field(default_factory=time.time)


# --------------------------------------------------------------------------
# Core JobState — the object LangGraph threads through every node (§5.1)
# --------------------------------------------------------------------------


class JobState(BaseModel):
    session_id: str = Field(default_factory=_new_id)
    trace_id: str = Field(default_factory=_new_id)

    parsed_resume: ParsedResume | None = None
    postings: list[JobPosting] = Field(default_factory=list)
    ats_results: dict[str, ATSResult] = Field(default_factory=dict)  # keyed by posting.id
    tailored: dict[str, TailoredResume] = Field(default_factory=dict)  # keyed by posting.id
    approvals: dict[str, ApprovalStatus] = Field(default_factory=dict)  # keyed by posting.id
    application_results: dict[str, dict] = Field(default_factory=dict)  # keyed by posting.id
    trace: list[TraceEvent] = Field(default_factory=list)

    current_step: str = "start"
    escalated: bool = False
    escalation_reason: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
