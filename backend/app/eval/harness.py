"""Evaluation harness (§7).

"An agent system without measurement is a demo, not engineering."
JobPilot tracks the metrics defined in the architecture doc's evaluation
table against small, hand-labeled evaluation sets checked into
``app/eval/data/``:

  Metric                    Method                                    Target
  job relevance precision   human-labeled sample of postings          >= 85%
  ATS score calibration     predicted vs. reference ATS score         +/- 7 points
  tailoring faithfulness    structural + semantic hallucination check 100%
  keyword-gap closure       missing_keywords present in tailored out  >= 80%
  manager gate accuracy     manager pass/fail vs. human review        >= 90%

Run with: ``python -m app.eval.harness``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

from app.agents.ats_scorer import score_resume_heuristic
from app.agents.faithfulness import check_faithfulness
from app.agents.job_search import rank_postings
from app.schemas.models import JobPosting, ParsedResume, TailoredResume

_DATA_DIR = Path(__file__).parent / "data"


def _load(name: str) -> list[dict]:
    return json.loads((_DATA_DIR / name).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# ATS score calibration — target +/- 7 points
# --------------------------------------------------------------------------


def eval_ats_calibration() -> dict:
    fixtures = _load("ats_calibration.json")
    errors = []
    for fx in fixtures:
        resume = ParsedResume.model_validate(fx["resume"])
        posting = JobPosting.model_validate(fx["posting"])
        result = score_resume_heuristic(resume, posting)
        errors.append(abs(result.score - fx["reference_score"]))

    within_tolerance = sum(1 for e in errors if e <= 7.0)
    return {
        "metric": "ATS score calibration",
        "target": "within +/-7 points",
        "n": len(fixtures),
        "mean_abs_error": round(mean(errors), 2) if errors else 0.0,
        "within_tolerance_pct": round(100 * within_tolerance / len(errors), 1) if errors else 0.0,
    }


# --------------------------------------------------------------------------
# Job relevance precision — target >= 85%
# --------------------------------------------------------------------------


def eval_job_relevance(threshold: float = 0.15) -> dict:
    fixtures = _load("job_relevance.json")
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for fx in fixtures:
        resume = ParsedResume.model_validate(fx["resume"])
        posting = JobPosting.model_validate(fx["posting"])
        ranked = rank_postings(resume, [posting])
        predicted_relevant = ranked[0].relevance_score >= threshold
        human_relevant = fx["human_relevant"]

        if predicted_relevant and human_relevant:
            true_positives += 1
        elif predicted_relevant and not human_relevant:
            false_positives += 1
        elif not predicted_relevant and human_relevant:
            false_negatives += 1

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0.0
    )
    return {
        "metric": "Job relevance precision",
        "target": ">= 85%",
        "n": len(fixtures),
        "precision_pct": round(precision * 100, 1),
        "false_negatives": false_negatives,
    }


# --------------------------------------------------------------------------
# Tailoring faithfulness — target 100%
# --------------------------------------------------------------------------


def eval_faithfulness() -> dict:
    fixtures = _load("faithfulness.json")
    passed = 0
    matched_expectation = 0
    semantic_judge_unavailable = 0

    for fx in fixtures:
        resume = ParsedResume.model_validate(fx["resume"])
        tailored = TailoredResume.model_validate(fx["tailored"])
        checked = check_faithfulness(resume, tailored)

        if "LLM error" in "; ".join(checked.faithfulness_violations):
            semantic_judge_unavailable += 1

        if checked.faithfulness_status.value == fx["expected_status"]:
            matched_expectation += 1
        if checked.faithfulness_status.value == "passed":
            passed += 1

    return {
        "metric": "Tailoring faithfulness",
        "target": "100% of bullets pass",
        "n": len(fixtures),
        "passed_pct": round(100 * passed / len(fixtures), 1) if fixtures else 0.0,
        "matched_expected_label_pct": round(100 * matched_expectation / len(fixtures), 1)
        if fixtures
        else 0.0,
        "semantic_judge_unavailable": semantic_judge_unavailable,  # LLM call failed (no key, quota, network, etc.)
    }


# --------------------------------------------------------------------------
# Keyword-gap closure — target >= 80%
# --------------------------------------------------------------------------


def eval_keyword_gap_closure() -> dict:
    fixtures = _load("keyword_gap_closure.json")
    ratios = []

    for fx in fixtures:
        missing = fx["missing_keywords"]
        tailored = TailoredResume.model_validate(fx["tailored"])
        surfaced_terms = {
            kw.lower() for b in tailored.bullets for kw in b.keywords_surfaced
        }
        blob = (
            " ".join(b.text for b in tailored.bullets) + " " + tailored.cover_letter
        ).lower()

        closed = sum(
            1 for kw in missing if kw.lower() in surfaced_terms or kw.lower() in blob
        )
        ratios.append(closed / len(missing) if missing else 1.0)

    return {
        "metric": "Keyword-gap closure",
        "target": ">= 80%",
        "n": len(fixtures),
        "closure_pct": round(100 * mean(ratios), 1) if ratios else 0.0,
    }


# --------------------------------------------------------------------------
# Manager gate accuracy — target >= 90%
# --------------------------------------------------------------------------


def eval_manager_gate_accuracy(threshold: float = 70.0) -> dict:
    fixtures = _load("manager_gate_accuracy.json")
    agree = 0

    for fx in fixtures:
        manager_decision = "pass" if fx["ats_score"] >= threshold else "fail"
        if manager_decision == fx["human_decision"]:
            agree += 1

    return {
        "metric": "Manager gate accuracy",
        "target": ">= 90%",
        "n": len(fixtures),
        "agreement_pct": round(100 * agree / len(fixtures), 1) if fixtures else 0.0,
    }


def run_all() -> list[dict]:
    return [
        eval_ats_calibration(),
        eval_job_relevance(),
        eval_faithfulness(),
        eval_keyword_gap_closure(),
        eval_manager_gate_accuracy(),
    ]


def _print_report(results: list[dict]) -> None:
    for r in results:
        metric = r.pop("metric")
        target = r.pop("target")
        print(f"\n{metric}  (target: {target})")
        for k, v in r.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    report = run_all()
    _print_report(report)
    sys.exit(0)
