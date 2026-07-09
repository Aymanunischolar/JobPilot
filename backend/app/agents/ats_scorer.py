"""ATS Scorer Agent (§4.4).

Estimates how a real Applicant Tracking System would score the current
resume against a specific job description, and returns the reasoning
(missing_keywords + fit_rationale), not just a number — both are required
inputs to the Tailor Agent, not optional metadata. The weighted signal
breakdown mirrors the table in the architecture doc:

  keyword coverage 40% · title/seniority 20% · experience 15%
  · education/cert 10% · formatting 15%
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.llm import LLMError, complete_json
from app.schemas.models import ATSResult, ATSSignalBreakdown, JobPosting, ParsedResume

_WEIGHTS = {
    "keyword_coverage": 0.40,
    "title_seniority_alignment": 0.20,
    "experience_match": 0.15,
    "education_match": 0.10,
    "formatting_compatibility": 0.15,
}

_STOPWORDS = {
    "the", "and", "for", "with", "you", "our", "are", "will", "have", "this",
    "that", "from", "your", "who", "job", "role", "team", "work", "years",
    "experience", "ability", "skills", "using", "including", "etc",
}

_YEARS_RE = re.compile(r"(\d+)\+?\s*(?:-\s*\d+\s*)?years?", re.IGNORECASE)


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]{2,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _extract_required_keywords(jd_text: str, top_n: int = 25) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]{2,}", jd_text.lower())
    freq: dict[str, int] = {}
    for t in tokens:
        if t in _STOPWORDS:
            continue
        freq[t] = freq.get(t, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:top_n]]


def _keyword_coverage(resume: ParsedResume, jd_text: str) -> tuple[float, list[str]]:
    required = _extract_required_keywords(jd_text)
    resume_terms = _tokenize(" ".join(resume.skills))
    for role in resume.roles:
        resume_terms |= _tokenize(" ".join(b.text for b in role.bullets))

    matched = [kw for kw in required if kw in resume_terms]
    missing = [kw for kw in required if kw not in resume_terms]
    coverage = len(matched) / len(required) if required else 1.0
    return coverage, missing


def _title_seniority_alignment(resume: ParsedResume, posting: JobPosting) -> float:
    if not resume.roles:
        return 0.0
    resume_title_tokens = _tokenize(resume.roles[0].title)
    jd_title_tokens = _tokenize(posting.title)
    if not jd_title_tokens:
        return 0.5
    overlap = resume_title_tokens & jd_title_tokens
    return min(1.0, len(overlap) / max(1, len(jd_title_tokens)))


def _parse_year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d{4}", value)
    return int(match.group(0)) if match else None


def _total_years_experience(resume: ParsedResume) -> float:
    total = 0.0
    now_year = datetime.now().year
    for role in resume.roles:
        start = _parse_year(role.start_date)
        end = _parse_year(role.end_date) or now_year
        if start:
            total += max(0, end - start)
    return total


def _experience_match(resume: ParsedResume, jd_text: str) -> float:
    required_years_match = _YEARS_RE.search(jd_text)
    if not required_years_match:
        return 0.75  # no explicit requirement stated — treat as neutral-positive
    required_years = float(required_years_match.group(1))
    candidate_years = _total_years_experience(resume)
    if required_years <= 0:
        return 1.0
    return max(0.0, min(1.0, candidate_years / required_years))


def _education_match(resume: ParsedResume, jd_text: str) -> float:
    jd_lower = jd_text.lower()
    degree_terms = ["bachelor", "master", "phd", "b.s.", "m.s.", "associate degree"]
    jd_requires_degree = any(term in jd_lower for term in degree_terms)
    has_degree = bool(resume.education)
    cert_terms = _tokenize(" ".join(resume.certifications))
    cert_bonus = 0.2 if cert_terms & _tokenize(jd_lower) else 0.0

    if not jd_requires_degree:
        return min(1.0, 0.8 + cert_bonus)
    return min(1.0, (1.0 if has_degree else 0.3) + cert_bonus)


def _formatting_compatibility(resume: ParsedResume) -> float:
    """Proxy for 'parseable sections, no tables/graphics' — a resume that
    yielded rich structured fields survived extraction cleanly."""
    score = 0.0
    score += 0.3 if resume.roles else 0.0
    score += 0.2 if resume.skills else 0.0
    score += 0.2 if resume.education else 0.0
    score += 0.15 if resume.email else 0.0
    score += 0.15 if all(b.text.strip() for role in resume.roles for b in role.bullets) else 0.0
    return min(1.0, score) or 0.5


def _fallback_rationale(posting: JobPosting, score: float, missing_keywords: list[str]) -> str:
    return (
        f"Scored {score:.0f}/100 against '{posting.title}'. "
        f"Missing {len(missing_keywords)} keyword(s) the JD emphasizes: "
        f"{', '.join(missing_keywords[:8]) or 'none'}."
    )


def score_resume_heuristic(resume: ParsedResume, posting: JobPosting) -> ATSResult:
    """The deterministic half of ATS scoring — no LLM call, so this is
    fast and free to run for every posting. ``fit_rationale`` starts as
    the heuristic fallback string and is upgraded in place by
    ``generate_rationales_batch`` for postings worth explaining well."""
    settings = get_settings()

    keyword_coverage, missing_keywords = _keyword_coverage(resume, posting.jd_text)
    title_seniority = _title_seniority_alignment(resume, posting)
    experience = _experience_match(resume, posting.jd_text)
    education = _education_match(resume, posting.jd_text)
    formatting = _formatting_compatibility(resume)

    breakdown = ATSSignalBreakdown(
        keyword_coverage=round(keyword_coverage * 100, 2),
        title_seniority_alignment=round(title_seniority * 100, 2),
        experience_match=round(experience * 100, 2),
        education_match=round(education * 100, 2),
        formatting_compatibility=round(formatting * 100, 2),
    )

    score = (
        keyword_coverage * _WEIGHTS["keyword_coverage"]
        + title_seniority * _WEIGHTS["title_seniority_alignment"]
        + experience * _WEIGHTS["experience_match"]
        + education * _WEIGHTS["education_match"]
        + formatting * _WEIGHTS["formatting_compatibility"]
    ) * 100

    return ATSResult(
        score=round(score, 2),
        missing_keywords=missing_keywords,
        fit_rationale=_fallback_rationale(posting, score, missing_keywords),
        passed_gate=score >= settings.ats_pass_threshold,
        signal_breakdown=breakdown,
    )


class _RationaleItem(BaseModel):
    posting_id: str
    fit_rationale: str


class _RationaleBatchOut(BaseModel):
    results: list[_RationaleItem] = Field(default_factory=list)


_RATIONALE_BATCH_SYSTEM_PROMPT = """You are an ATS analyst. You'll be given
a candidate summary and a list of job postings, each with its computed
match score and missing keywords. For EACH posting, write a 2-3 sentence
fit_rationale explaining the score in plain language — reference the
specific role/company and the specific missing keywords, don't write a
generic template.

Return ONLY JSON: {"results": [{"posting_id": str, "fit_rationale": str}]}
One entry per posting_id given, in any order."""


def generate_rationales_batch(
    resume: ParsedResume, postings: list[JobPosting], results: dict[str, ATSResult]
) -> None:
    """Fills in a real fit_rationale for a batch of postings with ONE LLM
    call instead of one call per posting — the dominant cost in a run
    scoring a couple dozen postings is round-trips, not tokens, so
    batching is the highest-leverage latency fix available here. Mutates
    ``results`` in place; postings not covered by the batch are left with
    their heuristic fallback string (already set by
    ``score_resume_heuristic``), so a batch failure degrades gracefully
    rather than blocking the pipeline."""
    if not postings:
        return

    listing = "\n\n".join(
        f"posting_id: {p.id}\n"
        f"Score: {results[p.id].score:.1f}/100\n"
        f"Missing keywords: {', '.join(results[p.id].missing_keywords[:15])}\n"
        f"Job title: {p.title} at {p.company}\n"
        f"JD excerpt: {p.jd_text[:800]}"
        for p in postings
        if p.id in results
    )
    user = (
        f"Candidate top skills: {', '.join(resume.skills[:10])}\n\n"
        f"POSTINGS:\n{listing}"
    )

    try:
        out = complete_json(_RATIONALE_BATCH_SYSTEM_PROMPT, user, _RationaleBatchOut)
    except LLMError:
        return  # every posting already has its heuristic fallback rationale

    for item in out.results:
        if item.posting_id in results:
            results[item.posting_id].fit_rationale = item.fit_rationale
