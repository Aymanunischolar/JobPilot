from app.agents.job_search import build_queries, dedup_postings, rank_postings
from app.schemas.models import JobPosting, ParsedResume, RoleExperience


def test_build_queries_uses_top_skills_and_latest_title():
    resume = ParsedResume(
        skills=["Python", "FastAPI", "PostgreSQL"],
        roles=[RoleExperience(title="Senior Backend Engineer", company="Acme")],
    )
    queries = build_queries(resume)
    assert queries
    assert any("Senior Backend Engineer" in q for q in queries)


def test_dedup_postings_collapses_mirrored_urls():
    postings = [
        JobPosting(
            source_url="https://boards.example.com/job/123?utm_source=agg",
            canonical_url="",
            jd_text="Backend Engineer role.",
            company="Acme",
            title="Backend Engineer",
        ),
        JobPosting(
            source_url="https://boards.example.com/job/123/",
            canonical_url="",
            jd_text="Backend Engineer role.",
            company="Acme",
            title="Backend Engineer",
        ),
    ]
    deduped = dedup_postings(postings)
    assert len(deduped) == 1


def test_rank_postings_orders_by_relevance_score():
    resume = ParsedResume(
        skills=["Python", "FastAPI", "PostgreSQL"],
        roles=[RoleExperience(title="Backend Engineer", company="Acme")],
    )
    strong = JobPosting(
        source_url="https://a.example.com/1",
        canonical_url="https://a.example.com/1",
        jd_text="Backend Engineer needed: Python, FastAPI, PostgreSQL.",
        company="A",
        title="Backend Engineer",
    )
    weak = JobPosting(
        source_url="https://b.example.com/2",
        canonical_url="https://b.example.com/2",
        jd_text="Warehouse associate, forklift certification required.",
        company="B",
        title="Warehouse Associate",
    )
    ranked = rank_postings(resume, [weak, strong])
    assert ranked[0].source_url == strong.source_url
