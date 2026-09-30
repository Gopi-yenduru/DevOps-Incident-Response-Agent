"""
Agent 5: Response Orchestrator

Executes automated response actions based on the incident analysis:
1. Creates a GitHub Issue with full diagnostic details
2. Sends a Telegram alert notification
3. Optionally creates a fix PR for trivial fixes with code snippets

This agent calls external services (GitHub, Telegram) — each action
is wrapped in its own try/except to ensure partial failures don't
block other actions.

Input:  Complete incident data from all prior agents.
Output: Summary of actions taken with URLs and status.
"""

import logging
from typing import Any

from config import get_settings

logger = logging.getLogger("devops_agent.agent.response_orchestrator")

settings = get_settings()

# ── Default output on failure ──────────────────────────────────────────
DEFAULT_OUTPUT: dict[str, Any] = {
    "github_issue_url": None,
    "github_pr_url": None,
    "telegram_sent": False,
    "slack_sent": False,
    "actions_taken": [],
}


async def orchestrate_response(
    incident_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute automated response actions for a diagnosed incident.

    Creates GitHub issues, sends Telegram alerts, and optionally
    creates fix PRs. Each action is independent — failure in one
    does not prevent others from executing.

    Args:
        incident_data: Combined output from all prior agents, containing:
            - anomaly report (severity, error_type, affected_service, etc.)
            - root cause analysis (root_cause, causal_chain, blast_radius)
            - fix suggestion (fix_summary, fix_steps, code_snippet, complexity)
            - app_name, incident_id, etc.

    Returns:
        Response summary dict with URLs and action list.
        Never raises — always returns a result dict.
    """
    result: dict[str, Any] = {
        "github_issue_url": None,
        "github_pr_url": None,
        "telegram_sent": False,
        "slack_sent": False,
        "actions_taken": [],
    }

    # ── 1. Create GitHub Issue ─────────────────────────────────────
    if settings.GITHUB_TOKEN and settings.GITHUB_REPO:
        try:
            from services.github_service import create_incident_issue

            issue_url = await create_incident_issue(incident_data)
            if issue_url:
                result["github_issue_url"] = issue_url
                result["actions_taken"].append("created_github_issue")
                logger.info(
                    f"[agent:response_orchestrator] GitHub issue created: {issue_url}"
                )
        except Exception as e:
            logger.error(
                f"[agent:response_orchestrator] GitHub issue creation failed: {e}",
                exc_info=True,
            )
            result["actions_taken"].append("github_issue_failed")
    else:
        logger.info(
            "[agent:response_orchestrator] GitHub integration not configured, skipping"
        )
        result["actions_taken"].append("github_not_configured")

    # ── 2. Create Fix PR (trivial fixes only) ──────────────────────
    complexity = incident_data.get("fix_complexity") or incident_data.get("complexity", "")
    code_snippet = incident_data.get("fix_code_snippet") or incident_data.get("code_snippet")

    if (
        settings.GITHUB_TOKEN
        and settings.GITHUB_REPO
        and complexity == "trivial"
        and code_snippet
    ):
        try:
            from services.github_service import create_fix_pr

            pr_url = await create_fix_pr(incident_data)
            if pr_url:
                result["github_pr_url"] = pr_url
                result["actions_taken"].append("created_github_pr")
                logger.info(
                    f"[agent:response_orchestrator] Fix PR created: {pr_url}"
                )
        except Exception as e:
            logger.error(
                f"[agent:response_orchestrator] Fix PR creation failed: {e}",
                exc_info=True,
            )
            result["actions_taken"].append("github_pr_failed")

    # ── 3. Send Telegram Alert ─────────────────────────────────────
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        try:
            from services.telegram_service import send_incident_alert

            telegram_sent = await send_incident_alert(incident_data)
            result["telegram_sent"] = telegram_sent
            if telegram_sent:
                result["actions_taken"].append("sent_telegram")
                logger.info("[agent:response_orchestrator] Telegram alert sent")
            else:
                result["actions_taken"].append("telegram_send_failed")
        except Exception as e:
            logger.error(
                f"[agent:response_orchestrator] Telegram alert failed: {e}",
                exc_info=True,
            )
            result["actions_taken"].append("telegram_failed")
    else:
        logger.info(
            "[agent:response_orchestrator] Telegram integration not configured, skipping"
        )
        result["actions_taken"].append("telegram_not_configured")

    # ── 4. Send Slack Alert ────────────────────────────────────────
    if settings.SLACK_WEBHOOK_URL:
        try:
            from services.slack_service import send_incident_alert as send_slack_alert

            slack_sent = await send_slack_alert(incident_data)
            result["slack_sent"] = slack_sent
            if slack_sent:
                result["actions_taken"].append("sent_slack")
                logger.info("[agent:response_orchestrator] Slack alert sent")
            else:
                result["actions_taken"].append("slack_send_failed")
        except Exception as e:
            logger.error(
                f"[agent:response_orchestrator] Slack alert failed: {e}",
                exc_info=True,
            )
            result["actions_taken"].append("slack_failed")
    else:
        logger.info(
            "[agent:response_orchestrator] Slack integration not configured, skipping"
        )
        result["actions_taken"].append("slack_not_configured")

    logger.info(
        f"[agent:response_orchestrator] completed | "
        f"actions={result['actions_taken']}"
    )

    return result
