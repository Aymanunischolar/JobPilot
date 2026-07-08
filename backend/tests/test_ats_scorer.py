from app.agents.ats_scorer import score_resume
from app.schemas.models import Bullet, JobPosting, ParsedResume, RoleExperience


def _strong_match_resume() -> ParsedResume:
    return ParsedResume(
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
        roles=[
            RoleExperience(
                title="Backend Engineer",
                company="Northwind",
                start_date="2021",
                end_date="Present",
                bullets=[
                    Bullet(text="Built REST APIs in Python and FastAPI serving 2M requests/day"),
                    Bullet(text="Deployed services to AWS using Docker containers"),
                ],
            )
        ],
        education=[],
        certifications=[],
    )


def _weak_match_resume() -> ParsedResume:
    return ParsedResume(
        skills=["Figma", "Sketch"],
        roles=[RoleExperience(title="Product Designer", company="PixelWorks")],
    )


def _backend_posting() -> JobPosting:
    return JobPosting(
        source_url="https://example.com/job/1",
        canonical_url="https://example.com/job/1",
        jd_text=(
            "Backend Engineer, 2+ years, Python, FastAPI, PostgreSQL, Docker, AWS. "
            "Bachelor's degree preferred."
        ),
        company="Example Corp",
        title="Backend Engineer",
    )


def test_strong_match_scores_higher_than_weak_match():
    posting = _backend_posting()
    strong = score_resume(_strong_match_resume(), posting)
    weak = score_resume(_weak_match_resume(), posting)
    assert strong.score > weak.score


def test_passed_gate_reflects_threshold():
    posting = _backend_posting()
    result = score_resume(_strong_match_resume(), posting)
    assert result.passed_gate == (result.score >= 70.0)


def test_missing_keywords_populated_for_weak_match():
    result = score_resume(_weak_match_resume(), _backend_posting())
    assert len(result.missing_keywords) > 0


def test_signal_breakdown_present():
    result = score_resume(_strong_match_resume(), _backend_posting())
    assert result.signal_breakdown.keyword_coverage >= 0
