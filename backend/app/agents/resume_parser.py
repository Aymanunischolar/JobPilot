"""Resume Parser Agent (§4.2).

Converts an unstructured resume (PDF/DOCX) into a typed ``ParsedResume``.
LLM extraction does the heavy lifting (skills, roles, achievements); a
regex/rule-based fallback fills in dates and contact fields the LLM
misses or gets wrong, mirroring the extraction-pipeline pattern this
project is modeled on (93% field-level accuracy in production).
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from app.core.hashing import sha256
from app.core.llm import LLMError, complete_json
from app.schemas.models import Bullet, Education, ParsedResume, RoleExperience

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
_DATE_RE = re.compile(
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\b\d{4}\b|Present|Current",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = """You are a precise resume-extraction engine. Extract the
candidate's structured profile from the raw resume text. Return ONLY a
JSON object matching this shape:

{
  "full_name": str | null,
  "email": str | null,
  "phone": str | null,
  "skills": [str],
  "roles": [
    {"title": str, "company": str, "start_date": str|null, "end_date": str|null,
     "bullets": [{"text": str, "quantified_metrics": [str]}]}
  ],
  "education": [
    {"institution": str, "degree": str|null, "field_of_study": str|null, "graduation_date": str|null}
  ],
  "certifications": [str]
}

Rules:
- Every bullet must be copied faithfully from the resume text — do not
  invent, embellish, or merge bullets from different roles.
- quantified_metrics captures numbers/percentages/dollar amounts present
  in that specific bullet (e.g. "40%", "$2M", "10k users"), verbatim.
- If a field is not present in the text, use null or an empty list.
"""


def extract_text(file_bytes: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        import pdfplumber

        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    if suffix in (".docx", ".doc"):
        import docx

        document = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in document.paragraphs)
    raise ValueError(f"Unsupported resume format: {suffix}")


def _regex_fallback_contact(raw_text: str, parsed: ParsedResume) -> None:
    """Fill in contact fields the LLM missed, in place."""
    if not parsed.email:
        match = _EMAIL_RE.search(raw_text)
        if match:
            parsed.email = match.group(0)
    if not parsed.phone:
        match = _PHONE_RE.search(raw_text)
        if match:
            parsed.phone = match.group(0).strip()


def _regex_fallback_dates(parsed: ParsedResume, raw_text: str) -> None:
    """If the LLM left a role's dates empty, try to recover them from the
    raw text near the role/company mention."""
    for role in parsed.roles:
        if role.start_date and role.end_date:
            continue
        window_match = re.search(re.escape(role.company or role.title), raw_text, re.IGNORECASE)
        if not window_match:
            continue
        window = raw_text[window_match.start() : window_match.start() + 200]
        spans = [m.group(0) for m in _DATE_RE.finditer(window)]
        if spans:
            role.start_date = role.start_date or spans[0]
            role.end_date = role.end_date or (spans[1] if len(spans) > 1 else "Present")


def parse_resume(file_bytes: bytes, filename: str) -> ParsedResume:
    raw_text = extract_text(file_bytes, filename)
    if not raw_text.strip():
        raise ValueError("No extractable text found in resume file")

    try:
        parsed = complete_json(_SYSTEM_PROMPT, raw_text, ParsedResume)
    except LLMError:
        # Degrade to a minimal skeleton so the pipeline can still surface
        # contact info via the regex fallback rather than hard-failing.
        parsed = ParsedResume()

    # Bullets from the LLM arrive without stable IDs assigned by our
    # factory (model_validate uses the JSON as-is) — regenerate to
    # guarantee every bullet has a unique, traceable ID.
    for role in parsed.roles:
        role.bullets = [
            Bullet(text=b.text, quantified_metrics=b.quantified_metrics) for b in role.bullets
        ]

    _regex_fallback_contact(raw_text, parsed)
    _regex_fallback_dates(parsed, raw_text)

    parsed.raw_text_hash = sha256(raw_text)
    return parsed
