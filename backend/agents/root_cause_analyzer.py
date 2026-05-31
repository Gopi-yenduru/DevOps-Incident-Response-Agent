"""
Agent 3: Root Cause Analyzer

Performs deep causal chain reasoning to identify the root cause of an incident.
Considers historical context to detect recurring patterns and assesses
the blast radius (scope of impact) across the system.

Input:  Anomaly report + correlation data + historical incident summary.
Output: Root cause analysis with causal chain, blast radius, and pattern detection.
"""

import json
import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from config import get_settings

logger = logging.getLogger("devops_agent.agent.root_cause_analyzer")

settings = get_settings()

# ── Default output on failure ──────────────────────────────────────────
DEFAULT_OUTPUT: dict[str, Any] = {
    "root_cause": "Unable to determine root cause",
    "causal_chain": ["Error detected", "Analysis inconclusive"],
    "blast_radius": "isolated",
    "historical_pattern": "first-occurrence",
    "confidence": 0.0,
}

# ── System Prompt with Few-Shot Examples ───────────────────────────────
SYSTEM_PROMPT = """You are an expert DevOps root cause analysis agent. Your job is to perform deep causal reasoning to identify the underlying root cause of production incidents.

You MUST respond with ONLY valid JSON — no markdown, no code fences, no explanation, no preamble. Just raw JSON.

Analysis methodology:
1. Start from the observed error and trace backward through potential causes
2. Consider infrastructure, application, and dependency layers
3. Use the "5 Whys" technique to drill down to the true root cause
4. Assess blast radius: how much of the system is affected
5. Check historical patterns: has this happened before?

Return:
- root_cause: concise description of the fundamental cause (not just the symptom)
- causal_chain: ordered list of steps from root cause → observed error (3-5 steps)
- blast_radius: "isolated" | "partial" | "system-wide"
  - isolated: single service or component affected
  - partial: multiple services or a critical subsystem affected
  - system-wide: entire platform or user-facing services affected
- historical_pattern: "first-occurrence" | "recurring (N times)" | "escalating"
- confidence: float 0.0-1.0

## Example 1

Anomaly report:
{"severity": "critical", "error_type": "ConnectionPoolExhausted", "affected_service": "auth-service", "error_message": "PostgreSQL connection pool exhausted, all 50 connections in use"}

Correlation data:
{"is_correlated": true, "correlated_incident_ids": ["inc-001"], "correlation_reason": "Related DB connection issues in user-service"}

Historical incidents:
[{"error_type": "ConnectionTimeout", "affected_service": "auth-service", "created_at": "2024-01-10", "root_cause": "Slow query in user lookup"},
 {"error_type": "ConnectionTimeout", "affected_service": "user-service", "created_at": "2024-01-12", "root_cause": "Missing index on users table"}]

Output:
{"root_cause": "PostgreSQL connection pool starvation caused by unoptimized queries holding connections too long. The users table likely has missing or degraded indexes causing full table scans, which hold connections for extended periods and prevent other services from acquiring connections.", "causal_chain": ["Missing or degraded database indexes on frequently-queried tables", "SELECT queries on users table degrade from milliseconds to seconds", "Long-running queries hold database connections beyond expected duration", "Connection pool (50 max) fills up as connections are not returned promptly", "auth-service and user-service cannot acquire new connections, causing cascading failures"], "blast_radius": "partial", "historical_pattern": "recurring (2 times)", "confidence": 0.91}

## Example 2

Anomaly report:
{"severity": "error", "error_type": "NullPointerException", "affected_service": "payment-service", "error_message": "NullPointerException at PaymentProcessor.validateCard line 89"}

Correlation data:
{"is_correlated": false, "correlated_incident_ids": []}

Historical incidents:
[]

Output:
{"root_cause": "Missing null-safety check in PaymentProcessor.validateCard() at line 89. The card validation method receives a null card object or null card field (likely card number or expiry date) from the upstream request, but does not validate input before accessing object properties.", "causal_chain": ["API request received with missing or null card data field", "Request passes through controller without input validation", "PaymentProcessor.validateCard() attempts to access properties on null card object", "NullPointerException thrown at line 89, transaction fails"], "blast_radius": "isolated", "historical_pattern": "first-occurrence", "confidence": 0.85}
"""


async def analyze_root_cause(
    anomaly_report: dict[str, Any],
    correlation_data: dict[str, Any],
    historical_incidents: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Perform root cause analysis using anomaly, correlation, and historical data.

    Args:
        anomaly_report: Output from the anomaly detector agent.
        correlation_data: Output from the incident correlator agent.
        historical_incidents: Summary of past incidents (same error type or service).

    Returns:
        Root cause analysis dict with causal chain, blast radius, and pattern.
        Returns DEFAULT_OUTPUT on any failure.
    """
    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.2,
            max_output_tokens=2048,
        )

        # Format historical context
        historical_context = (
            json.dumps(historical_incidents, indent=2, default=str)
            if historical_incidents
            else "[]  (no prior incidents for this error type or service)"
        )

        prompt = (
            f"Anomaly report:\n"
            f"{json.dumps(anomaly_report, indent=2)}\n\n"
            f"Correlation data:\n"
            f"{json.dumps(correlation_data, indent=2)}\n\n"
            f"Historical incidents (same error type or service):\n"
            f"{historical_context}\n\n"
            f"Perform deep root cause analysis. Identify the fundamental cause, "
            f"build the causal chain, assess blast radius, and check for "
            f"historical patterns."
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
            "root_cause": str(result.get("root_cause", DEFAULT_OUTPUT["root_cause"])),
            "causal_chain": list(result.get("causal_chain", DEFAULT_OUTPUT["causal_chain"])),
            "blast_radius": str(result.get("blast_radius", "isolated")),
            "historical_pattern": str(result.get("historical_pattern", "first-occurrence")),
            "confidence": max(0.0, min(1.0, float(result.get("confidence", 0.0)))),
        }

        # Validate blast_radius enum
        if validated["blast_radius"] not in ("isolated", "partial", "system-wide"):
            validated["blast_radius"] = "isolated"

        # Ensure causal_chain items are strings
        validated["causal_chain"] = [str(step) for step in validated["causal_chain"]]

        logger.info(
            f"[agent:root_cause_analyzer] blast_radius={validated['blast_radius']} "
            f"pattern={validated['historical_pattern']} "
            f"confidence={validated['confidence']}"
        )

        return validated

    except json.JSONDecodeError as e:
        logger.error(f"[agent:root_cause_analyzer] JSON parse error: {e}")
        return {**DEFAULT_OUTPUT, "root_cause": f"Analysis failed: JSON parse error"}
    except Exception as e:
        logger.error(f"[agent:root_cause_analyzer] failed: {e}", exc_info=True)
        return {**DEFAULT_OUTPUT, "root_cause": f"Analysis failed: {str(e)}"}
