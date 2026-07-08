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


def _tavily_search(query: str, max_results: int = 10) -> list[dict]:
    from tavily import TavilyClient

    settings = get_settings()
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    client = TavilyClient(api_key=settings.tavily_api_key)
    resp = client.search(query=query, max_results=max_results, search_depth="advanced")
    return resp.get("results", [])


def search_jobs(resume: ParsedResume, max_results_per_query: int = 10) -> list[JobPosting]:
    """Full Job Search Agent pipeline: build queries -> call Tavily ->
    parse into JobPosting -> dedup -> rank."""
    queries = build_queries(resume)
    raw_postings: list[JobPosting] = []

    for query in queries:
        for result in _tavily_search(query, max_results=max_results_per_query):
            raw_postings.append(
                JobPosting(
                    source_url=result.get("url", ""),
                    canonical_url=canonicalize_url(result.get("url", "")),
                    jd_text=result.get("content", ""),
                    company=result.get("company", "") or "",
                    title=result.get("title", "") or query,
                )
            )

    deduped = dedup_postings(raw_postings)
    return rank_postings(resume, deduped)
