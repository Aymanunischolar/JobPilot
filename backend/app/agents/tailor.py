"""Tailor Agent (§4.5).

Produces one tailored resume and one cover-letter draft per qualifying
job description, constrained to reordering and reweighting real
experience — never inventing it. Every generated bullet must cite the
``source_bullet_id`` of the ParsedResume bullet it was derived from; the
Manager's faithfulness check (§6.2) is what actually enforces this, not
prompt instruction alone. The Tailor Agent uses ``missing_keywords`` from
the ATS Scorer to decide what to surface or reword — never what to
fabricate.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.core.llm import LLMError, complete_json
from app.schemas.models import (
    ATSResult,
    JobPosting,
    ParsedResume,
    TailoredBullet,
    TailoredResume,
)

_SYSTEM_PROMPT = """You are a resume tailoring engine. You will be given a
candidate's existing resume bullets (each with a stable ID), a target job
description, and a list of keywords the ATS flagged as missing.

Your ONLY job is to select and reword a subset of the EXISTING bullets to
better surface skills/keywords that are truthfully already reflected in
that bullet's original text. You may:
  - reorder bullets
  - reword a bullet to surface a missing keyword IF AND ONLY IF that
    keyword's underlying skill/fact is already present in the original
    bullet text
  - lightly tighten phrasing

You may NEVER:
  - invent a metric, tool, skill, or outcome not present in the source
    bullet
  - merge two source bullets into a fabricated new claim
  - cite a source_bullet_id that was not given to you

Return ONLY JSON matching:
{
  "bullets": [
    {"source_bullet_id": str, "text": str, "keywords_surfaced": [str]}
  ],
  "cover_letter": str
}

The cover_letter should be 3-4 short paragraphs, grounded only in facts
present in the provided resume bullets and skills — no fabricated claims.
"""


class _TailorOut(BaseModel):
    bullets: list[TailoredBullet]
    cover_letter: str


def _build_diff_summary(
    resume: ParsedResume, tailored_bullets: list[TailoredBullet]
) -> str:
    source_bullets = resume.all_bullets()
    lines = []
    for tb in tailored_bullets:
        original = source_bullets.get(tb.source_bullet_id)
        original_text = original.text if original else "<unknown source bullet>"
        if original_text.strip() == tb.text.strip():
            continue
        lines.append(f"- ORIGINAL: {original_text}\n  TAILORED: {tb.text}")
    if not lines:
        return "No wording changes — bullets reordered/selected as-is."
    return "\n".join(lines)


def tailor_resume(
    resume: ParsedResume, posting: JobPosting, ats_result: ATSResult
) -> TailoredResume:
    source_bullets = resume.all_bullets()
    bullet_listing = "\n".join(
        f"[{bid}] {b.text} (metrics: {', '.join(b.quantified_metrics) or 'none'})"
        for bid, b in source_bullets.items()
    )

    user = (
        f"CANDIDATE SKILLS: {', '.join(resume.skills)}\n\n"
        f"SOURCE BULLETS (id: text):\n{bullet_listing}\n\n"
        f"TARGET ROLE: {posting.title} at {posting.company}\n"
        f"JOB DESCRIPTION:\n{posting.jd_text[:3000]}\n\n"
        f"ATS FIT RATIONALE: {ats_result.fit_rationale}\n"
        f"MISSING KEYWORDS TO CONSIDER SURFACING (only if truthfully "
        f"present in a source bullet): {', '.join(ats_result.missing_keywords)}\n"
    )

    try:
        out = complete_json(_SYSTEM_PROMPT, user, _TailorOut)
    except LLMError:
        # Degrade to a safe no-op tailoring: pass through original bullets
        # verbatim (100% faithful by construction) rather than fail closed.
        out = _TailorOut(
            bullets=[
                TailoredBullet(source_bullet_id=bid, text=b.text, keywords_surfaced=[])
                for bid, b in source_bullets.items()
            ],
            cover_letter="",
        )

    diff_summary = _build_diff_summary(resume, out.bullets)

    return TailoredResume(
        bullets=out.bullets,
        cover_letter=out.cover_letter,
        diff_summary=diff_summary,
    )
