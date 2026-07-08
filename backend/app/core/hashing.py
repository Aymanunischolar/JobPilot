"""Canonicalization and hashing utilities used for dedup and traceability.

- ``raw_text_hash`` on ParsedResume lets the faithfulness checker prove a
  tailored resume was derived from a specific source document (§5.2).
- ``canonical_url`` + ``jd_hash`` on JobPosting let the Job Search Agent
  dedup postings mirrored across multiple job aggregators (§4.3).
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Query params that vary per-visit/session but don't change the underlying
# posting — stripped before canonicalization so mirrors collapse to one URL.
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "ref", "refid", "src", "trk", "session_id",
}


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonicalize_url(url: str) -> str:
    """Strip tracking params, fragment, trailing slash, and lowercase the
    host so the same posting linked from different aggregators collapses
    to a single canonical form."""
    parts = urlsplit(url.strip())
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query.sort()
    path = parts.path.rstrip("/") or "/"
    netloc = parts.netloc.lower()
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query), ""))


def normalize_jd_text(jd_text: str) -> str:
    """Collapse whitespace/case so near-duplicate JDs hash identically even
    when formatting differs slightly between sources."""
    return re.sub(r"\s+", " ", jd_text.strip().lower())


def jd_fingerprint(jd_text: str) -> str:
    return sha256(normalize_jd_text(jd_text))
