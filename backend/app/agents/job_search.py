"""Job Search Agent (§4.3).

Finds and ranks candidate postings using Tavily as the web-search tool.
Query construction pulls from the ParsedResume's top skills, most recent
title, and seniority rather than a single static keyword string. Ranking
is a hybrid of keyword overlap (for ATS realism) and embedding similarity
(to catch relevant roles phrased differently). Dedup uses canonical-URL
and near-duplicate JD hashing so the same posting mirrored across
aggregators only surfaces once.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit

import numpy as np

from app.core.config import get_settings
from app.core.hashing import canonicalize_url, jd_fingerprint
from app.schemas.models import JobPosting, ParsedResume

_SENIORITY_WORDS = [
    "intern", "junior", "associate", "mid-level", "senior", "staff",
    "principal", "lead", "manager", "director", "vp", "head of",
]


def _infer_seniority(resume: ParsedResume) -> str:
    if not resume.roles:
        return ""
    latest_title = resume.roles[0].title.lower()
    for word in _SENIORITY_WORDS:
        if word in latest_title:
            return word
    return ""


def build_queries(resume: ParsedResume, max_queries: int = 3) -> list[str]:
    """Build search queries from top skills + most recent title +
    seniority — not a single static keyword string (§4.3)."""
    latest_title = resume.roles[0].title if resume.roles else ""
    seniority = _infer_seniority(resume)
    top_skills = resume.skills[:5]

    queries: list[str] = []
    if latest_title:
        queries.append(f'"{latest_title}" jobs {" ".join(top_skills[:3])}'.strip())
    for skill_pair in zip(top_skills[::2], top_skills[1::2]):
        queries.append(f"{seniority} {latest_title} {' '.join(skill_pair)} job openings".strip())
    if not queries:
        queries.append("open roles " + " ".join(top_skills))
    return queries[:max_queries]


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]{1,}", text.lower()))


def _keyword_overlap_score(resume_terms: set[str], jd_text: str) -> float:
    jd_terms = _tokenize(jd_text)
    if not resume_terms or not jd_terms:
        return 0.0
    overlap = resume_terms & jd_terms
    return len(overlap) / len(resume_terms)


def _term_vector(terms: set[str], vocab: list[str]) -> np.ndarray:
    return np.array([1.0 if t in terms else 0.0 for t in vocab])


def _embedding_similarity(resume_terms: set[str], jd_text: str) -> float:
    """Lightweight bag-of-words cosine similarity used as a stand-in for a
    true embedding model — swap for OpenAI/Gemini embeddings by replacing
    this function; the ranking formula in ``rank_postings`` is unaffected."""
    jd_terms = _tokenize(jd_text)
    vocab = list(resume_terms | jd_terms)
    if not vocab:
        return 0.0
    a = _term_vector(resume_terms, vocab)
    b = _term_vector(jd_terms, vocab)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def rank_postings(resume: ParsedResume, postings: list[JobPosting]) -> list[JobPosting]:
    """Hybrid score = 0.5 * keyword overlap + 0.5 * embedding-style
    similarity, so ATS-realistic keyword matches and semantically similar
    but differently-phrased roles both surface (§4.3)."""
    resume_terms = set(resume.skills)
    if resume.roles:
        resume_terms |= _tokenize(resume.roles[0].title)

    for posting in postings:
        kw_score = _keyword_overlap_score({t.lower() for t in resume_terms}, posting.jd_text)
        emb_score = _embedding_similarity({t.lower() for t in resume_terms}, posting.jd_text)
        posting.relevance_score = round(0.5 * kw_score + 0.5 * emb_score, 4)

    return sorted(postings, key=lambda p: p.relevance_score, reverse=True)


def dedup_postings(postings: list[JobPosting]) -> list[JobPosting]:
    """Collapse postings that share a canonical URL or a near-duplicate JD
    hash, keeping the first (highest-ranked, if called after ranking)
    occurrence (§4.3)."""
    seen_urls: set[str] = set()
    seen_jds: set[str] = set()
    deduped: list[JobPosting] = []
    for posting in postings:
        posting.canonical_url = canonicalize_url(posting.source_url)
        posting.jd_hash = jd_fingerprint(posting.jd_text)
        if posting.canonical_url in seen_urls or posting.jd_hash in seen_jds:
            continue
        seen_urls.add(posting.canonical_url)
        seen_jds.add(posting.jd_hash)
        deduped.append(posting)
    return deduped


_HOST_STOPWORDS = {
    "www", "jobs", "careers", "career", "job", "apply", "us", "en",
    "com", "org", "net", "io", "co", "gov", "edu",
}


def _infer_company_from_url(url: str) -> str:
    """Tavily's search results don't include a company field, so this is
    the best zero-cost signal available: the site's own domain name is
    usually the company or the job board, which still beats a blank
    field in the UI."""
    host = urlsplit(url).netloc.lower()
    parts = [p for p in host.split(".") if p and p not in _HOST_STOPWORDS]
    if not parts:
        return ""
    return parts[0].replace("-", " ").title()


# General web search on a "<title> jobs" query pulls in a lot of content
# that isn't a job posting at all — courses, explainer articles, YouTube
# videos, social media, framework docs. None of these have a real JD to
# score against, so they just fail the ATS gate and dilute the results.
# Company career pages live on arbitrary domains and can't be enumerated,
# so this excludes known non-job content sources rather than trying to
# allowlist job boards.
_EXCLUDED_SEARCH_DOMAINS = [
    "youtube.com", "instagram.com", "facebook.com", "twitter.com", "x.com",
    "coursera.org", "udemy.com", "medium.com", "reddit.com", "wikipedia.org",
    "tiktok.com", "pinterest.com", "quora.com",
]


def _tavily_search(query: str, max_results: int = 10) -> list[dict]:
    from tavily import TavilyClient

    settings = get_settings()
    client = TavilyClient(api_key=settings.tavily_api_key)
    resp = client.search(
        query=query,
        max_results=max_results,
        search_depth="advanced",
        exclude_domains=_EXCLUDED_SEARCH_DOMAINS,
    )
    return resp.get("results", [])


def search_jobs(resume: ParsedResume, max_results_per_query: int = 10) -> list[JobPosting]:
    """Full Job Search Agent pipeline: build queries -> call Tavily ->
    parse into JobPosting -> dedup -> rank."""
    settings = get_settings()
    if not settings.tavily_api_key:
        # A missing key is a config problem, not "no results found" — it
        # must surface clearly (routes.py maps RuntimeError to a 503),
        # not get silently swallowed by the per-query error handling below.
        raise RuntimeError("TAVILY_API_KEY is not set")

    queries = build_queries(resume)
    raw_postings: list[JobPosting] = []

    # Each query is an independent network round-trip to Tavily — running
    # them concurrently instead of one-after-another turns N sequential
    # round-trips into roughly the cost of the slowest one.
    with ThreadPoolExecutor(max_workers=max(1, len(queries))) as pool:
        futures = {pool.submit(_tavily_search, q, max_results_per_query): q for q in queries}
        for future in as_completed(futures):
            query = futures[future]
            try:
                query_results = future.result()
            except Exception:
                # One query failing (rate limit, transient network error)
                # shouldn't sink results from the others.
                continue
            for result in query_results:
                url = result.get("url", "")
                raw_postings.append(
                    JobPosting(
                        source_url=url,
                        canonical_url=canonicalize_url(url),
                        jd_text=result.get("content", ""),
                        company=result.get("company") or _infer_company_from_url(url),
                        title=result.get("title", "") or query,
                    )
                )

    deduped = dedup_postings(raw_postings)
    return rank_postings(resume, deduped)
