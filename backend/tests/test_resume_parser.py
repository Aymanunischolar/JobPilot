from app.agents.resume_parser import _heuristic_extract_skills, _heuristic_parse

_SAMPLE_RESUME_TEXT = """Jane Doe
jane.doe@example.com

PROFESSIONAL SUMMARY
Backend engineer with 5 years of experience.

TECHNICAL SKILLS
Python, FastAPI, PostgreSQL, Docker, AWS

PROFESSIONAL EXPERIENCE
Senior Backend Engineer June 2021 - Present
Acme Systems
- Built REST APIs in Python and FastAPI serving 2M requests per day
- Migrated deployments to Docker containers on AWS infrastructure

EDUCATION
Bachelor of Science in Computer Science
"""


def test_heuristic_extract_skills_matches_known_keywords():
    skills = _heuristic_extract_skills(_SAMPLE_RESUME_TEXT)
    assert "Python" in skills
    assert "FastAPI" in skills
    assert "Docker" in skills
    assert "AWS" in skills


def test_heuristic_extract_skills_avoids_substring_false_positives():
    # "Java" must not match inside "JavaScript", and vice versa shouldn't
    # cause duplicate/garbled entries.
    skills = _heuristic_extract_skills("Experienced with JavaScript and TypeScript.")
    assert "JavaScript" in skills
    assert "TypeScript" in skills
    assert "Java" not in skills


def test_heuristic_parse_extracts_name_and_role():
    parsed = _heuristic_parse(_SAMPLE_RESUME_TEXT)
    assert parsed.full_name == "Jane Doe"
    assert len(parsed.roles) == 1
    assert parsed.roles[0].title == "Senior Backend Engineer"
    assert parsed.roles[0].start_date is not None
    assert len(parsed.roles[0].bullets) >= 1


def test_heuristic_parse_never_raises_on_sparse_text():
    parsed = _heuristic_parse("Just a name\nwith no other structure at all.")
    assert parsed.skills == []
    assert parsed.roles == []
