"""
Slack notification service.

Sends formatted incident alerts to a Slack channel via an Incoming Webhook URL.
Uses httpx for async HTTP requests. Mirrors telegram_service so the response
orchestrator can dispatch to both channels independently.
"""

import logging
from typing import Any

import httpx

from config import get_settings

logger = logging.getLogger("devops_agent.service.slack")

settings = get_settings()


async def send_incident_alert(incident_data: dict[str, Any]) -> bool:
    """
    Send a formatted incident alert to the configured Slack webhook.

    Args:
        incident_data: Combined incident data from all agents.

    Returns:
        True if the message was accepted by Slack, False otherwise.
    """
    try:
        if not settings.SLACK_WEBHOOK_URL:
            logger.warning("[slack] Webhook URL not configured")
            return False

        severity = incident_data.get("severity", "error").upper()
        severity_emoji = {
            "CRITICAL": "🔴",
            "ERROR": "🟠",
            "WARNING": "🟡",
            "NORMAL": "🟢",
        }.get(severity, "⚪")

        root_cause = incident_data.get("root_cause", "N/A")
        if len(root_cause) > 300:
            root_cause = root_cause[:300] + "..."

        github_issue_url = incident_data.get("github_issue_url")
        github_pr_url = incident_data.get("github_pr_url")

        # Slack Block Kit payload for a readable, structured message.
        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚨 Incident Detected"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*App:*\n{incident_data.get('app_name', 'unknown')}"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity_emoji} {severity}"},
                    {"type": "mrkdwn", "text": f"*Service:*\n{incident_data.get('affected_service', 'unknown')}"},
                    {"type": "mrkdwn", "text": f"*Error:*\n{incident_data.get('error_type', 'Unknown')}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Root Cause:*\n{root_cause}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Fix:* {incident_data.get('fix_summary', 'N/A')}\n"
                        f"*Complexity:* {incident_data.get('fix_complexity', 'unknown')} · "
                        f"*Est. Time:* {incident_data.get('estimated_time', 'unknown')}"
                    ),
                },
            },
        ]

        links = []
        if github_issue_url:
            links.append(f"<{github_issue_url}|GitHub Issue>")
        if github_pr_url:
            links.append(f"<{github_pr_url}|Fix PR>")
        if links:
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": " · ".join(links)}],
                }
            )

        payload = {
            "text": f"Incident detected in {incident_data.get('affected_service', 'unknown')} ({severity})",
            "blocks": blocks,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(settings.SLACK_WEBHOOK_URL, json=payload)

        # Slack Incoming Webhooks return HTTP 200 with the body "ok" on success.
        if response.status_code == 200 and response.text.strip() == "ok":
            logger.info("[slack] Alert sent successfully")
            return True

        logger.error(
            f"[slack] Send failed: HTTP {response.status_code}: {response.text[:200]}"
        )
        return False

    except httpx.TimeoutException:
        logger.error("[slack] Request timed out")
        return False
    except Exception as e:
        logger.error(f"[slack] Failed to send alert: {e}", exc_info=True)
        return False
