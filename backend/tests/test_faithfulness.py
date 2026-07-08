from app.agents.faithfulness import structural_check
from app.schemas.models import Bullet, ParsedResume, RoleExperience, TailoredBullet, TailoredResume


def _resume() -> ParsedResume:
    return ParsedResume(
        skills=["Python"],
        roles=[
            RoleExperience(
                title="Engineer",
                company="Acme",
                bullets=[Bullet(id="b1", text="Built REST APIs")],
            )
        ],
    )


def test_structural_check_passes_for_valid_source_id():
    resume = _resume()
    tailored = TailoredResume(
        bullets=[TailoredBullet(source_bullet_id="b1", text="Built REST APIs")]
    )
    assert structural_check(resume, tailored) == []


def test_structural_check_flags_unknown_source_id():
    resume = _resume()
    tailored = TailoredResume(
        bullets=[TailoredBullet(source_bullet_id="does-not-exist", text="Fabricated bullet")]
    )
    violations = structural_check(resume, tailored)
    assert len(violations) == 1
    assert "does-not-exist" in violations[0]
