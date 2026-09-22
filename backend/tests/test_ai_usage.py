from types import SimpleNamespace

from app.services.ai_service import _provider_usage


def test_extracts_reasoning_token_usage_when_provider_returns_it():
    response = SimpleNamespace(usage=SimpleNamespace(
        prompt_tokens=120,
        completion_tokens=80,
        total_tokens=200,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=35),
    ))
    assert _provider_usage(response) == {
        "input_tokens": 120, "output_tokens": 80, "total_tokens": 200, "reasoning_tokens": 35,
    }


def test_handles_provider_response_without_usage_details():
    assert _provider_usage(SimpleNamespace(usage=None))["reasoning_tokens"] is None
