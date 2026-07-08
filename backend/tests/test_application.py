import pytest

from app.agents.application import ApplicationNotApprovedError, classify_channel, submit_application
from app.schemas.models import (
    ApprovalDecision,
    ApprovalStatus,
    JobPosting,
    TailoredResume,
)


def _posting(url: str = "https://boards.example.com/job/1") -> JobPosting:
    return JobPosting(
        source_url=url,
        canonical_url=url,
        jd_text="Some job",
        company="Acme",
        title="Engineer",
    )


def test_classify_channel_defaults_to_major_job_board_when_not_allowlisted():
    assert classify_channel(_posting()).value == "major_job_board"


@pytest.mark.asyncio
async def test_submit_application_refuses_without_approval():
    approval = ApprovalStatus(decision=ApprovalDecision.PENDING)
    with pytest.raises(ApplicationNotApprovedError):
        await submit_application(_posting(), TailoredResume(), approval, "resume.pdf")


@pytest.mark.asyncio
async def test_submit_application_refuses_when_rejected():
    approval = ApprovalStatus(decision=ApprovalDecision.REJECTED)
    with pytest.raises(ApplicationNotApprovedError):
        await submit_application(_posting(), TailoredResume(), approval, "resume.pdf")
