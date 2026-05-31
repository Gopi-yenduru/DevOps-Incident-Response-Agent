"""
Telegram notification service.

Sends formatted incident alerts to a Telegram chat/channel
via the Telegram Bot API. Uses httpx for async HTTP requests.
"""

import logging
from typing import Any

import httpx

from config import get_settings

logger = logging.getLogger("devops_agent.service.telegram")

settings = get_settings()

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


async def send_incident_alert(incident_data: dict[str, Any]) -> bool:
    """
    Send a formatted incident alert to the configured Telegram chat.

    Args:
        incident_data: Combined incident data from all agents.

    Returns:
        True if the message was sent successfully, False otherwise.
    """
    try:
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            logger.warning("[telegram] Bot token or chat ID not configured")
            return False

        severity = incident_data.get("severity", "error").upper()
        severity_emoji = {
            "CRITICAL": "🔴",
            "ERROR": "🟠",
            "WARNING": "🟡",
            "NORMAL": "🟢",
        }.get(severity, "⚪")

        # Build message
        root_cause = incident_data.get("root_cause", "N/A")
        if len(root_cause) > 200:
            root_cause = root_cause[:200] + "..."

        github_issue_url = incident_data.get("github_issue_url")
        github_link = f"\n🔗 GitHub Issue: {github_issue_url}" if github_issue_url else ""

        github_pr_url = incident_data.get("github_pr_url")
        pr_link = f"\n🔀 Fix PR: {github_pr_url}" if github_pr_url else ""

        anomaly_conf = incident_data.get("anomaly_confidence", 0)
        fix_conf = incident_data.get("fix_confidence", 0)
        avg_confidence = int(((anomaly_conf + fix_conf) / 2) * 100)

        message = f"""🚨 *INCIDENT DETECTED*

*App:* {incident_data.get("app_name", "unknown")}
*Severity:* {severity_emoji} {severity}
*Error:* {incident_data.get("error_type", "Unknown")} in {incident_data.get("affected_service", "unknown")}
*Time:* {incident_data.get("created_at", "just now")}

📋 *Root Cause:*
{root_cause}

🔧 *Fix:* {incident_data.get("fix_summary", "N/A")}
*Complexity:* {incident_data.get("fix_complexity", "unknown")}
*Est\\. Time:* {incident_data.get("estimated_time", "unknown")}
{github_link}{pr_link}

*Confidence:* {avg_confidence}%"""

        # Send via Telegram Bot API
        url = f"{TELEGRAM_API_BASE.format(token=settings.TELEGRAM_BOT_TOKEN)}/sendMessage"

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logger.info("[telegram] Alert sent successfully")
                    return True
                else:
                    logger.error(f"[telegram] API returned error: {data}")
                    return False
            else:
                logger.error(
                    f"[telegram] HTTP {response.status_code}: {response.text}"
                )
                return False

    except httpx.TimeoutException:
        logger.error("[telegram] Request timed out")
        return False
    except Exception as e:
        logger.error(f"[telegram] Failed to send alert: {e}", exc_info=True)
        return False


async def send_resolution_alert(incident_data: dict[str, Any]) -> bool:
    """
    Send a resolution notification when an incident is marked resolved.

    Args:
        incident_data: Incident data including MTTR.

    Returns:
        True if sent successfully.
    """
    try:
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            return False

        mttr = incident_data.get("mttr_seconds")
        mttr_display = _format_duration(mttr) if mttr else "N/A"

        message = f"""✅ *INCIDENT RESOLVED*

*App:* {incident_data.get("app_name", "unknown")}
*Error:* {incident_data.get("error_type", "Unknown")} in {incident_data.get("affected_service", "unknown")}
*MTTR:* {mttr_display}
*Status:* Resolved"""

        url = f"{TELEGRAM_API_BASE.format(token=settings.TELEGRAM_BOT_TOKEN)}/sendMessage"

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
            )
            return response.status_code == 200 and response.json().get("ok", False)

    except Exception as e:
        logger.error(f"[telegram] Resolution alert failed: {e}")
        return False


def _format_duration(seconds: int) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
