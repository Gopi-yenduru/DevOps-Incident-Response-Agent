"""
Tests for the anomaly detector agent.

The Gemini client is fully mocked, so these tests exercise the agent's own
parsing, validation, clamping, and fallback logic — never the network.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from agents.anomaly_detector import detect_anomaly, DEFAULT_OUTPUT


def _patch_llm(content: str):
    """Return a patch context replacing the Gemini client with a stub that
    responds with the given raw content string."""
    instance = MagicMock()
    instance.ainvoke = AsyncMock(return_value=MagicMock(content=content))
    factory = MagicMock(return_value=instance)
    return patch("agents.anomaly_detector.ChatGoogleGenerativeAI", factory)


async def test_parses_valid_json_response():
    raw = (
        '{"is_anomaly": true, "severity": "critical", '
        '"error_type": "ConnectionPoolExhausted", '
        '"affected_service": "auth-service", '
        '"error_message": "pool exhausted", '
        '"frequency": "one-time", "confidence": 0.96}'
    )
    with _patch_llm(raw):
        result = await detect_anomaly("FATAL: pool exhausted")

    assert result["is_anomaly"] is True
    assert result["severity"] == "critical"
    assert result["affected_service"] == "auth-service"
    assert result["confidence"] == 0.96


async def test_strips_markdown_code_fences():
    raw = (
        "```json\n"
        '{"is_anomaly": true, "severity": "error", "error_type": "X", '
        '"affected_service": "svc", "error_message": "m", '
        '"frequency": "one-time", "confidence": 0.5}\n'
        "```"
    )
    with _patch_llm(raw):
        result = await detect_anomaly("some log")

    assert result["is_anomaly"] is True
    assert result["severity"] == "error"


async def test_confidence_is_clamped_to_unit_interval():
    raw = (
        '{"is_anomaly": true, "severity": "error", "error_type": "X", '
        '"affected_service": "svc", "error_message": "m", '
        '"frequency": "one-time", "confidence": 4.5}'
    )
    with _patch_llm(raw):
        result = await detect_anomaly("log")

    assert result["confidence"] == 1.0


async def test_invalid_severity_is_coerced_to_error():
    raw = (
        '{"is_anomaly": true, "severity": "apocalyptic", "error_type": "X", '
        '"affected_service": "svc", "error_message": "m", '
        '"frequency": "one-time", "confidence": 0.7}'
    )
    with _patch_llm(raw):
        result = await detect_anomaly("log")

    assert result["severity"] == "error"


async def test_malformed_json_falls_back_to_default_output():
    with _patch_llm("this is not json at all"):
        result = await detect_anomaly("log")

    # Falls back to the safe default (treated as non-anomaly) rather than raising.
    assert result["is_anomaly"] == DEFAULT_OUTPUT["is_anomaly"]
    assert "JSON parse error" in result["error_message"]
