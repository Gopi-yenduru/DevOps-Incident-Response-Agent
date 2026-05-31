"""
Agent 2: Incident Correlator

Finds related active incidents by comparing error types, affected services,
error messages, and timing. Groups related incidents using LLM reasoning
to reduce noise and identify systemic issues.

Input:  Anomaly report + list of recent open incidents (within correlation window).
Output: Correlation assessment with related incident IDs and reasoning.
"""

import json
import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from config import get_settings

logger = logging.getLogger("devops_agent.agent.incident_correlator")

settings = get_settings()

# ── Default output on failure ──────────────────────────────────────────
DEFAULT_OUTPUT: dict[str, Any] = {
    "is_correlated": False,
    "correlated_incident_ids": [],
    "correlation_reason": "Unable to determine correlation",
    "is_new_incident": True,
    "confidence": 0.0,
}

# ── System Prompt with Few-Shot Examples ───────────────────────────────
SYSTEM_PROMPT = """You are an expert DevOps incident correlation agent. Your job is to determine if a newly detected anomaly is related to any existing open incidents.

You MUST respond with ONLY valid JSON — no markdown, no code fences, no explanation, no preamble. Just raw JSON.

Correlation criteria (check all):
1. Same error_type (e.g., both are ConnectionTimeout)
2. Same affected_service (e.g., both affect auth-service)
3. Similar error_message (semantic similarity, not exact match)
4. Temporal proximity (occurred within a short time window)
5. Causal relationship (one error could cause the other, e.g., DB down → auth failure)

Return:
- is_correlated: boolean — true if this anomaly relates to any existing incident
- correlated_incident_ids: list of related incident ID strings
- correlation_reason: explanation of why these incidents are related
- is_new_incident: boolean — true if this should create a new incident (even if correlated, may still be new)
- confidence: float 0.0-1.0

## Example 1

New anomaly:
{"error_type": "ConnectionTimeout", "affected_service": "auth-service", "error_message": "Database connection pool exhausted after 30s"}

Recent open incidents:
[{"id": "inc-001", "error_type": "ConnectionTimeout", "affected_service": "user-service", "error_message": "Database connection refused on port 5432", "created_at": "2024-01-15T14:20:00Z"}]

Output:
{"is_correlated": true, "correlated_incident_ids": ["inc-001"], "correlation_reason": "Both incidents involve database connection failures (ConnectionTimeout) affecting services that depend on the same PostgreSQL instance. The auth-service pool exhaustion and user-service connection refusal likely share a common root cause: database overload or network issue.", "is_new_incident": true, "confidence": 0.91}

## Example 2

New anomaly:
{"error_type": "NullPointerException", "affected_service": "payment-service", "error_message": "NullPointerException at PaymentProcessor.validateCard line 89"}

Recent open incidents:
[{"id": "inc-002", "error_type": "OutOfMemoryError", "affected_service": "auth-service", "error_message": "Java heap space exhausted in AuthController", "created_at": "2024-01-15T14:10:00Z"}]

Output:
{"is_correlated": false, "correlated_incident_ids": [], "correlation_reason": "The NullPointerException in payment-service is unrelated to the OutOfMemoryError in auth-service. Different error types, different services, and no apparent causal chain between them.", "is_new_incident": true, "confidence": 0.88}
"""


async def correlate_incident(
    anomaly_report: dict[str, Any],
    recent_incidents: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Check if a new anomaly correlates with existing open incidents.

    Args:
        anomaly_report: Output from the anomaly detector agent.
        recent_incidents: List of recent open incident summaries from the DB
                         (within the correlation window).

    Returns:
        Correlation assessment dict with related IDs and reasoning.
        Returns DEFAULT_OUTPUT on any failure.
    """
    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.1,
            max_output_tokens=1024,
        )

        # Format the context for the LLM
        incidents_context = (
            json.dumps(recent_incidents, indent=2, default=str)
            if recent_incidents
            else "[]  (no recent open incidents)"
        )

        prompt = (
            f"New anomaly detected:\n"
            f"{json.dumps(anomaly_report, indent=2)}\n\n"
            f"Recent open incidents (within correlation window):\n"
            f"{incidents_context}\n\n"
            f"Determine if this new anomaly is correlated with any existing incidents."
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        response = await llm.ainvoke(messages)
        raw_content = response.content.strip()

        # Strip markdown code fences
        if raw_content.startswith("```"):
            raw_content = raw_content.split("\n", 1)[-1]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3].strip()

        result = json.loads(raw_content)

        # Validate and normalize
        validated: dict[str, Any] = {
            "is_correlated": bool(result.get("is_correlated", False)),
            "correlated_incident_ids": list(result.get("correlated_incident_ids", [])),
            "correlation_reason": str(result.get("correlation_reason", "")),
            "is_new_incident": bool(result.get("is_new_incident", True)),
            "confidence": max(0.0, min(1.0, float(result.get("confidence", 0.0)))),
        }

        # Ensure correlated IDs are strings
        validated["correlated_incident_ids"] = [
            str(cid) for cid in validated["correlated_incident_ids"]
        ]

        logger.info(
            f"[agent:incident_correlator] is_correlated={validated['is_correlated']} "
            f"related={len(validated['correlated_incident_ids'])} "
            f"confidence={validated['confidence']}"
        )

        return validated

    except json.JSONDecodeError as e:
        logger.error(f"[agent:incident_correlator] JSON parse error: {e}")
        return {**DEFAULT_OUTPUT, "correlation_reason": f"JSON parse error: {str(e)}"}
    except Exception as e:
        logger.error(f"[agent:incident_correlator] failed: {e}", exc_info=True)
        return {**DEFAULT_OUTPUT, "correlation_reason": f"Agent error: {str(e)}"}
