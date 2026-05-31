"""
Agent 4: Fix Suggestion Agent

Generates actionable fix recommendations based on the root cause analysis.
Provides step-by-step instructions, code snippets when applicable,
complexity assessment, time estimates, and preventive measures.

Input:  Anomaly report + root cause analysis.
Output: Fix recommendation with steps, code, complexity, and prevention.
"""

import json
import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from config import get_settings

logger = logging.getLogger("devops_agent.agent.fix_suggestion")

settings = get_settings()

# ── Default output on failure ──────────────────────────────────────────
DEFAULT_OUTPUT: dict[str, Any] = {
    "fix_summary": "Unable to generate fix suggestion",
    "fix_steps": ["Investigate the error manually", "Check application logs for details"],
    "code_snippet": None,
    "complexity": "moderate",
    "estimated_time": "unknown",
    "preventive_measure": "Add monitoring and alerting for this error type",
    "confidence": 0.0,
}

# ── System Prompt with Few-Shot Examples ───────────────────────────────
SYSTEM_PROMPT = """You are an expert DevOps fix recommendation agent. Your job is to suggest actionable, specific fixes for production incidents based on root cause analysis.

You MUST respond with ONLY valid JSON — no markdown, no code fences, no explanation, no preamble. Just raw JSON.

Guidelines:
- Fix steps should be specific and actionable (not vague advice)
- Include code snippets when a code change would fix the issue
- Be realistic about complexity and time estimates
- Always suggest a preventive measure to avoid recurrence

Return:
- fix_summary: one-sentence summary of the fix
- fix_steps: ordered list of specific steps to resolve the issue (3-6 steps)
- code_snippet: code fix if applicable (string), or null if no code change needed
- complexity: "trivial" | "moderate" | "complex"
  - trivial: config change, restart, or simple code fix (< 30 min)
  - moderate: requires investigation, testing, possibly a deploy (30 min - 2 hours)
  - complex: architectural change, multi-service coordination, or risky fix (> 2 hours)
- estimated_time: human-readable time estimate (e.g., "15 minutes", "1-2 hours")
- preventive_measure: what to do to prevent this from happening again
- confidence: float 0.0-1.0

## Example 1

Anomaly:
{"severity": "critical", "error_type": "ConnectionPoolExhausted", "affected_service": "auth-service", "error_message": "PostgreSQL connection pool exhausted, all 50 connections in use"}

Root cause:
{"root_cause": "PostgreSQL connection pool starvation caused by unoptimized queries holding connections too long", "causal_chain": ["Missing database indexes", "Slow queries hold connections", "Pool fills up", "Service cannot acquire connections"], "blast_radius": "partial"}

Output:
{"fix_summary": "Add missing database indexes and increase connection pool size with query timeout enforcement", "fix_steps": ["Identify slow queries using PostgreSQL pg_stat_statements: SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10", "Add missing indexes based on slow query analysis: focus on WHERE and JOIN columns in the users and sessions tables", "Increase connection pool max_size from 50 to 100 in auth-service database config", "Add connection timeout of 30s to prevent queries from holding connections indefinitely", "Deploy changes and monitor connection pool utilization via pg_stat_activity"], "code_snippet": "# database.py - Add connection pool settings\\nimport sqlalchemy\\n\\nengine = sqlalchemy.create_engine(\\n    DATABASE_URL,\\n    pool_size=100,\\n    max_overflow=20,\\n    pool_timeout=30,\\n    pool_recycle=3600,\\n    pool_pre_ping=True,\\n)", "complexity": "moderate", "estimated_time": "1-2 hours", "preventive_measure": "Set up connection pool monitoring with alerts when utilization exceeds 80%. Add database query performance regression tests to CI pipeline.", "confidence": 0.89}

## Example 2

Anomaly:
{"severity": "error", "error_type": "NullPointerException", "affected_service": "payment-service", "error_message": "NullPointerException at PaymentProcessor.validateCard line 89"}

Root cause:
{"root_cause": "Missing null-safety check in PaymentProcessor.validateCard()", "causal_chain": ["Null card data in request", "No input validation", "NPE at line 89"], "blast_radius": "isolated"}

Output:
{"fix_summary": "Add null-safety validation in PaymentProcessor.validateCard() before accessing card properties", "fix_steps": ["Add input validation at the controller level to reject requests with missing card data", "Add null checks in PaymentProcessor.validateCard() before accessing card properties", "Add unit tests for null/empty card scenarios", "Deploy and verify with test transactions"], "code_snippet": "# PaymentProcessor.java\\npublic ValidationResult validateCard(Card card) {\\n    if (card == null) {\\n        return ValidationResult.invalid(\\\"Card data is required\\\");\\n    }\\n    if (card.getNumber() == null || card.getNumber().isEmpty()) {\\n        return ValidationResult.invalid(\\\"Card number is required\\\");\\n    }\\n    if (card.getExpiryDate() == null) {\\n        return ValidationResult.invalid(\\\"Expiry date is required\\\");\\n    }\\n    // ... existing validation logic\\n}", "complexity": "trivial", "estimated_time": "15-30 minutes", "preventive_measure": "Enable static analysis tools (SpotBugs/NullAway) in CI to catch potential NullPointerExceptions before deployment.", "confidence": 0.93}
"""


async def suggest_fix(
    anomaly_report: dict[str, Any],
    root_cause_analysis: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate fix recommendations based on anomaly and root cause data.

    Args:
        anomaly_report: Output from the anomaly detector agent.
        root_cause_analysis: Output from the root cause analyzer agent.

    Returns:
        Fix recommendation dict with steps, code, complexity, and prevention.
        Returns DEFAULT_OUTPUT on any failure.
    """
    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.2,
            max_output_tokens=2048,
        )

        prompt = (
            f"Anomaly report:\n"
            f"{json.dumps(anomaly_report, indent=2)}\n\n"
            f"Root cause analysis:\n"
            f"{json.dumps(root_cause_analysis, indent=2)}\n\n"
            f"Generate a specific, actionable fix recommendation with "
            f"step-by-step instructions and code if applicable."
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
            "fix_summary": str(result.get("fix_summary", DEFAULT_OUTPUT["fix_summary"])),
            "fix_steps": list(result.get("fix_steps", DEFAULT_OUTPUT["fix_steps"])),
            "code_snippet": result.get("code_snippet"),
            "complexity": str(result.get("complexity", "moderate")),
            "estimated_time": str(result.get("estimated_time", "unknown")),
            "preventive_measure": str(result.get("preventive_measure", "")),
            "confidence": max(0.0, min(1.0, float(result.get("confidence", 0.0)))),
        }

        # Validate complexity enum
        if validated["complexity"] not in ("trivial", "moderate", "complex"):
            validated["complexity"] = "moderate"

        # Ensure fix_steps are strings
        validated["fix_steps"] = [str(step) for step in validated["fix_steps"]]

        # Normalize code_snippet
        if validated["code_snippet"] is not None:
            validated["code_snippet"] = str(validated["code_snippet"])
            if not validated["code_snippet"].strip():
                validated["code_snippet"] = None

        logger.info(
            f"[agent:fix_suggestion] complexity={validated['complexity']} "
            f"has_code={validated['code_snippet'] is not None} "
            f"confidence={validated['confidence']}"
        )

        return validated

    except json.JSONDecodeError as e:
        logger.error(f"[agent:fix_suggestion] JSON parse error: {e}")
        return {**DEFAULT_OUTPUT, "fix_summary": f"Fix generation failed: JSON parse error"}
    except Exception as e:
        logger.error(f"[agent:fix_suggestion] failed: {e}", exc_info=True)
        return {**DEFAULT_OUTPUT, "fix_summary": f"Fix generation failed: {str(e)}"}
