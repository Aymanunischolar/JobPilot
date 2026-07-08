"""Application Agent (§4.6).

Handles the mechanical part of applying — filling forms via Playwright —
strictly after human approval, and only auto-submits on an explicit
allow-list (§6.3):

  - Company career-page form, no bot protection, in allow-list:
    auto-fill + auto-submit permitted after approval.
  - Major job board (LinkedIn, Indeed, etc.): auto-fill only, human
    clicks the final Submit.
  - Email-based application: draft composed for review, human sends.

This module has no code path that reaches Playwright without a prior
``ApprovalDecision.APPROVED`` on the posting — that boundary is enforced
one layer up by the Manager graph (§6.1), and re-asserted here as a
defense-in-depth guard.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from app.core.config import get_settings
from app.schemas.models import (
    ApprovalDecision,
    ApprovalStatus,
    Channel,
    JobPosting,
    TailoredResume,
)


class ApplicationNotApprovedError(RuntimeError):
    pass


def classify_channel(posting: JobPosting) -> Channel:
    """Determine which §6.3 bucket a posting falls into. A posting's host
    must be on the configured allow-list to be treated as an
    auto-submittable career page; everything else defaults to the safer
    auto-fill-only major-job-board behavior."""
    settings = get_settings()
    host = urlsplit(posting.canonical_url or posting.source_url).netloc.lower()
    if host in settings.allowlist_hosts:
        return Channel.CAREER_PAGE_ALLOWLISTED
    if "mailto:" in posting.source_url.lower():
        return Channel.EMAIL
    return Channel.MAJOR_JOB_BOARD


def can_auto_submit(posting: JobPosting) -> bool:
    settings = get_settings()
    host = urlsplit(posting.canonical_url or posting.source_url).netloc.lower()
    return host in settings.allowlist_hosts


async def submit_application(
    posting: JobPosting,
    tailored: TailoredResume,
    approval: ApprovalStatus,
    resume_file_path: str,
) -> dict:
    """Fill (and, only when allow-listed, submit) a job application via
    Playwright. Raises ``ApplicationNotApprovedError`` if no approval is
    on record — this function must never be reachable from a graph edge
    that bypasses the Human Approval Gate node (§6.1)."""
    if approval.decision != ApprovalDecision.APPROVED:
        raise ApplicationNotApprovedError(
            f"Refusing to act on posting {posting.id}: approval decision is "
            f"{approval.decision.value!r}, not 'approved'."
        )

    channel = classify_channel(posting)
    auto_submit = channel == Channel.CAREER_PAGE_ALLOWLISTED and can_auto_submit(posting)

    if channel == Channel.EMAIL:
        return {
            "posting_id": posting.id,
            "channel": channel.value,
            "action": "draft_composed",
            "auto_submitted": False,
            "cover_letter": tailored.cover_letter,
        }

    from playwright.async_api import async_playwright

    result = {
        "posting_id": posting.id,
        "channel": channel.value,
        "action": "form_filled",
        "auto_submitted": False,
    }

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(posting.source_url, wait_until="domcontentloaded")

            await _fill_common_fields(page, resume_file_path, tailored)

            if auto_submit:
                submit_button = page.locator(
                    "button[type=submit], input[type=submit]"
                ).first
                if await submit_button.count() > 0:
                    await submit_button.click()
                    result["action"] = "form_submitted"
                    result["auto_submitted"] = True
        finally:
            await browser.close()

    return result


async def _fill_common_fields(page, resume_file_path: str, tailored: TailoredResume) -> None:
    """Best-effort form fill — targets common field name/id patterns.
    Real career-page forms vary widely; production use would extend this
    with a per-domain adapter registry."""
    file_input = page.locator("input[type=file]").first
    if await file_input.count() > 0:
        await file_input.set_input_files(resume_file_path)

    cover_letter_field = page.locator(
        "textarea[name*=cover], textarea[id*=cover]"
    ).first
    if await cover_letter_field.count() > 0 and tailored.cover_letter:
        await cover_letter_field.fill(tailored.cover_letter)
