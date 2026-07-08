"""Hallucination / faithfulness checker (§6.2).

Before any TailoredResume reaches the human, the Manager runs a two-part
check:

  1. Structural — every source_bullet_id in the tailored output must
     exist in the original ParsedResume; any bullet without a valid
     source ID fails the gate automatically.
  2. Semantic — an LLM-as-judge compares each tailored bullet against its
     cited source bullet and flags additions of unverifiable metrics,
     skills, or claims not present in the source.

Failures are routed back to the Tailor Agent with the specific violating
bullet, not a generic "try again" — this keeps retries efficient and
keeps a clear audit trail of what was rejected and why.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.llm import LLMError, complete_json
from app.schemas.models import FaithfulnessStatus, ParsedResume, TailoredResume

_JUDGE_SYSTEM_PROMPT = """You are a strict fact-checking judge for resume
tailoring. For each (source, tailored) bullet pair, decide whether the
tailored bullet introduces ANY claim — a metric, tool, skill, title,
scope word ("led", "managed"), or outcome — that is not supported by the
source bullet text. Paraphrasing and reordering are fine; new unverifiable
substance is not.

Return ONLY JSON:
{
  "results": [
    {"source_bullet_id": str, "faithful": bool, "reason": str}
  ]
}
"""


class _JudgeResult(BaseModel):
    source_bullet_id: str
    faithful: bool
    reason: str = ""


class _JudgeOut(BaseModel):
    results: list[_JudgeResult] = Field(default_factory=list)


def structural_check(resume: ParsedResume, tailored: TailoredResume) -> list[str]:
    """Returns a list of violation strings — empty if every cited
    source_bullet_id exists in the original resume."""
    valid_ids = set(resume.all_bullets().keys())
    violations = []
    for tb in tailored.bullets:
        if tb.source_bullet_id not in valid_ids:
            violations.append(
                f"bullet cites unknown source_bullet_id={tb.source_bullet_id!r}: {tb.text!r}"
            )
    return violations


def semantic_check(resume: ParsedResume, tailored: TailoredResume) -> list[str]:
    """LLM-as-judge pass — only run on bullets that passed the structural
    check, since a judge can't compare against a source that doesn't
    exist."""
    source_bullets = resume.all_bullets()
    pairs = [
        (tb.source_bullet_id, source_bullets[tb.source_bullet_id].text, tb.text)
        for tb in tailored.bullets
        if tb.source_bullet_id in source_bullets
    ]
    if not pairs:
        return []

    listing = "\n".join(
        f"[{bid}] SOURCE: {src}\n[{bid}] TAILORED: {tgt}" for bid, src, tgt in pairs
    )
    try:
        out = complete_json(_JUDGE_SYSTEM_PROMPT, listing, _JudgeOut)
    except LLMError:
        # Fail closed on the semantic layer only if we can't verify at
        # all — surface as an escalation rather than silently passing.
        return [
            "semantic faithfulness judge unavailable (LLM error) — "
            "escalate for manual review"
        ]

    violations = [
        f"bullet {r.source_bullet_id!r} failed semantic check: {r.reason}"
        for r in out.results
        if not r.faithful
    ]
    return violations


def check_faithfulness(resume: ParsedResume, tailored: TailoredResume) -> TailoredResume:
    """Runs both checks and mutates+returns ``tailored`` with the final
    ``faithfulness_status`` and ``faithfulness_violations`` populated."""
    structural_violations = structural_check(resume, tailored)
    if structural_violations:
        tailored.faithfulness_status = FaithfulnessStatus.FAILED_STRUCTURAL
        tailored.faithfulness_violations = structural_violations
        return tailored

    semantic_violations = semantic_check(resume, tailored)
    if semantic_violations:
        tailored.faithfulness_status = FaithfulnessStatus.FAILED_SEMANTIC
        tailored.faithfulness_violations = semantic_violations
        return tailored

    tailored.faithfulness_status = FaithfulnessStatus.PASSED
    tailored.faithfulness_violations = []
    return tailored
