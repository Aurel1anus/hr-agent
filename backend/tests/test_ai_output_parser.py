from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import AgentRun
from app.services.ai_output_parser import AIParseError, parse_json_output
from app.services.agent_service import CopilotAIResult, RequirementProfileAIResult, _finish_success, validate_copilot, validate_requirement
from app.schemas import AssessmentResult
from app.services.agent_service import validate_assessment


def test_parses_direct_json_without_modification():
    assert parse_json_output('{"intent":"CREATE_TODO"}') == {"intent": "CREATE_TODO"}


def test_parses_markdown_json():
    assert parse_json_output('```json\n{"intent":"CREATE_TODO"}\n```') == {"intent": "CREATE_TODO"}


def test_extracts_json_from_explanatory_text():
    assert parse_json_output('结果如下： {"intent":"CREATE_TODO"}') == {"intent": "CREATE_TODO"}


def test_detects_truncated_json():
    with pytest.raises(AIParseError) as error:
        parse_json_output('{"must_have": [')
    assert error.value.code == "AI_OUTPUT_TRUNCATED"


def test_rejects_non_json_output():
    with pytest.raises(AIParseError) as error:
        parse_json_output('我无法生成结果')
    assert error.value.code == "AI_JSON_PARSE_ERROR"


def test_requirement_semantic_limit_rejects_overlong_skill_list():
    result = RequirementProfileAIResult(summary="有效画像", skills=[str(index) for index in range(21)])
    with pytest.raises(ValueError, match="skills"):
        validate_requirement(result)


def test_run_output_serializes_datetimes_for_json_column():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        run = AgentRun(agent_type="requirement_generation", model_name="test", status="running", started_at=datetime.now())
        db.add(run); db.commit()
        _finish_success(db, run, {"created_at": datetime(2026, 9, 22, 13, 25)}, False)
        assert db.get(AgentRun, run.id).output_json["created_at"] == "2026-09-22T13:25:00"


def test_assessment_recommendation_requires_machine_readable_enum():
    result = AssessmentResult(recommendation="建议进入面试", overall_score=65, summary="需要进一步核验")
    with pytest.raises(ValueError, match="recommendation"):
        validate_assessment(result)


def test_copilot_does_not_require_unused_assessment_recommendation():
    result = CopilotAIResult(summary="建议核验项目经验", strengths=[], risks=[], missing_information=[], verification_questions=[])
    validate_copilot(result)
