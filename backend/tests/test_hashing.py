from app.core.hashing import canonicalize_url, jd_fingerprint, sha256


def test_canonicalize_url_strips_tracking_params_and_fragment():
    a = canonicalize_url("https://Boards.example.com/job/123?utm_source=agg&ref=xyz#apply")
    b = canonicalize_url("https://boards.example.com/job/123/")
    assert a == b


def test_canonicalize_url_keeps_meaningful_query_params():
    a = canonicalize_url("https://boards.example.com/job?id=123")
    b = canonicalize_url("https://boards.example.com/job?id=456")
    assert a != b


def test_jd_fingerprint_ignores_whitespace_and_case_differences():
    a = jd_fingerprint("Senior   Engineer\nBuild things.")
    b = jd_fingerprint("senior engineer build things.")
    assert a == b


def test_sha256_deterministic():
    assert sha256("hello") == sha256("hello")
    assert sha256("hello") != sha256("world")
