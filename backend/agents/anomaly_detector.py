"""
Agent 1: Log Anomaly Detector

Classifies log severity, extracts error details, and determines
whether a log entry represents a genuine anomaly requiring investigation.

Input:  Raw log line(s) from a monitored application.
Output: Structured anomaly report with severity, error type, affected service,
        frequency assessment, and confidence score.
"""

import json
import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from config import get_settings

logger = logging.getLogger("devops_agent.agent.anomaly_detector")

settings = get_settings()

# ── Default output on failure ──────────────────────────────────────────
DEFAULT_OUTPUT: dict[str, Any] = {
    "is_anomaly": False,
    "severity": "normal",
    "error_type": "unknown",
    "affected_service": "unknown",
    "error_message": "",
    "frequency": "one-time",
    "confidence": 0.0,
}

# ── System Prompt with Few-Shot Examples ───────────────────────────────
SYSTEM_PROMPT = """You are an expert DevOps log anomaly detection agent. Your job is to analyze application log entries and determine if they represent anomalies that need investigation.

You MUST respond with ONLY valid JSON — no markdown, no code fences, no explanation, no preamble. Just raw JSON.

Analyze the log entry and return:
- is_anomaly: boolean — true if the log indicates an error, failure, or abnormal condition
- severity: "critical" | "error" | "warning" | "normal"
- error_type: short classification (e.g., "ConnectionTimeout", "OutOfMemoryError", "NullPointerException", "AuthenticationFailure")
- affected_service: the service or component name extracted from the log
- error_message: the core error description extracted from the log
- frequency: "one-time" | "recurring" | "escalating" — based on patterns in the log content
- confidence: float 0.0-1.0 — how confident you are in the classification

Severity guidelines:
- critical: System down, data loss risk, complete service failure, FATAL errors
- error: Feature broken, exceptions, 500 errors, connection failures
- warning: Degraded performance, timeouts, retries, high latency
- normal: Informational, debug, successful operations

## Example 1

Input log:
"2024-01-15 14:23:11 FATAL: terminating connection due to administrator command — PostgreSQL connection pool exhausted, all 50 connections in use, auth-service unable to process requests"

Output:
{"is_anomaly": true, "severity": "critical", "error_type": "ConnectionPoolExhausted", "affected_service": "auth-service", "error_message": "PostgreSQL connection pool exhausted, all 50 connections in use, service unable to process requests", "frequency": "one-time", "confidence": 0.96}

## Example 2

Input log:
"2024-01-15 14:23:11 INFO: Successfully processed 1,247 requests in the last 5 minutes. Average response time: 45ms. No errors detected."

Output:
{"is_anomaly": false, "severity": "normal", "error_type": "none", "affected_service": "request-handler", "error_message": "", "frequency": "one-time", "confidence": 0.98}
"""


async def detect_anomaly(log_text: str) -> dict[str, Any]:
    """
    Analyze a raw log entry for anomalies using the Gemini LLM.

    Args:
        log_text: Raw log line or batch of log lines to analyze.

    Returns:
        Structured anomaly report dict with severity, error details,
        and confidence score. Returns DEFAULT_OUTPUT on any failure.
    """
    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.1,
            max_output_tokens=1024,
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Analyze this log entry:\n\n{log_text}"),
        ]

        response = await llm.ainvoke(messages)
        raw_content = response.content.strip()

        # Strip markdown code fences if the model wraps them anyway
        if raw_content.startswith("```"):
            raw_content = raw_content.split("\n", 1)[-1]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3].strip()

        result = json.loads(raw_content)

        # Validate required fields
        validated: dict[str, Any] = {
            "is_anomaly": bool(result.get("is_anomaly", False)),
            "severity": result.get("severity", "normal"),
            "error_type": result.get("error_type", "unknown"),
            "affected_service": result.get("affected_service", "unknown"),
            "error_message": result.get("error_message", ""),
            "frequency": result.get("frequency", "one-time"),
            "confidence": float(result.get("confidence", 0.0)),
        }

        # Clamp confidence to [0.0, 1.0]
        validated["confidence"] = max(0.0, min(1.0, validated["confidence"]))

        # Validate severity enum
        if validated["severity"] not in ("critical", "error", "warning", "normal"):
            validated["severity"] = "error"

        # Validate frequency enum
        if validated["frequency"] not in ("one-time", "recurring", "escalating"):
            validated["frequency"] = "one-time"

        logger.info(
            f"[agent:anomaly_detector] is_anomaly={validated['is_anomaly']} "
            f"severity={validated['severity']} confidence={validated['confidence']}"
        )

        return validated

    except json.JSONDecodeError as e:
        logger.error(f"[agent:anomaly_detector] JSON parse error: {e}")
        return {**DEFAULT_OUTPUT, "error_message": f"JSON parse error: {str(e)}"}
    except Exception as e:
        logger.error(f"[agent:anomaly_detector] failed: {e}", exc_info=True)
        return {**DEFAULT_OUTPUT, "error_message": f"Agent error: {str(e)}"}
