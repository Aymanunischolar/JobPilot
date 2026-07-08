from app.schemas.models import (
    ApprovalDecision,
    ApprovalStatus,
    Bullet,
    JobState,
    ParsedResume,
    RoleExperience,
)


def test_parsed_resume_all_bullets_indexes_by_id():
    resume = ParsedResume(
        skills=["Python"],
        roles=[
            RoleExperience(
                title="Engineer",
                company="Acme",
                bullets=[Bullet(id="b1", text="Did a thing")],
            )
        ],
    )
    bullets = resume.all_bullets()
    assert set(bullets.keys()) == {"b1"}
    assert bullets["b1"].text == "Did a thing"


def test_job_state_roundtrips_through_json():
    state = JobState()
    state.approvals["posting-1"] = ApprovalStatus(decision=ApprovalDecision.APPROVED)

    restored = JobState.model_validate_json(state.model_dump_json())

    assert restored.session_id == state.session_id
    assert restored.approvals["posting-1"].decision == ApprovalDecision.APPROVED
