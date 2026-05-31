"""
GitHub integration service.

Creates formatted incident issues and fix pull requests
using the PyGithub library. All operations are wrapped in
try/except to ensure the pipeline continues on GitHub failures.
"""

import logging
from typing import Any, Optional

from github import Github, GithubException

from config import get_settings

logger = logging.getLogger("devops_agent.service.github")

settings = get_settings()


def _get_github_client() -> tuple[Github, Any]:
    """Get authenticated GitHub client and repository."""
    g = Github(settings.GITHUB_TOKEN)
    repo = g.get_repo(settings.GITHUB_REPO)
    return g, repo


async def create_incident_issue(incident_data: dict[str, Any]) -> Optional[str]:
    """
    Create a GitHub issue with full incident diagnostic details.

    Args:
        incident_data: Combined incident data from all agents.

    Returns:
        GitHub issue URL string, or None on failure.
    """
    try:
        _, repo = _get_github_client()

        severity = incident_data.get("severity", "error").upper()
        error_type = incident_data.get("error_type", "Unknown Error")
        affected_service = incident_data.get("affected_service", "unknown")
        title = f"[{severity}] {error_type} in {affected_service}"

        # Build causal chain markdown
        causal_chain = incident_data.get("causal_chain", [])
        causal_chain_md = "\n".join(
            f"{i+1}. {step}" for i, step in enumerate(causal_chain)
        ) if causal_chain else "Analysis pending"

        # Build fix steps markdown
        fix_steps = incident_data.get("fix_steps", [])
        fix_steps_md = "\n".join(
            f"{i+1}. {step}" for i, step in enumerate(fix_steps)
        ) if fix_steps else "No fix steps available"

        # Build code snippet section
        code_snippet = incident_data.get("fix_code_snippet") or incident_data.get("code_snippet")
        code_section = ""
        if code_snippet:
            code_section = f"""
### Code Fix
```
{code_snippet}
```
"""

        # Confidence display
        anomaly_conf = incident_data.get("anomaly_confidence", 0)
        rca_conf = incident_data.get("rootcause_confidence", 0)
        fix_conf = incident_data.get("fix_confidence", 0)

        # Severity emoji
        severity_emoji = {
            "CRITICAL": "🔴",
            "ERROR": "🟠",
            "WARNING": "🟡",
            "NORMAL": "🟢",
        }.get(severity, "⚪")

        body = f"""## 🚨 Incident Summary

**Severity:** {severity_emoji} {severity}
**Service:** {affected_service}
**Error Type:** {error_type}
**Detected:** {incident_data.get("created_at", "just now")}
**Anomaly Confidence:** {int(anomaly_conf * 100)}%

**Error Message:**
> {incident_data.get("error_message", "N/A")}

## 🔍 Root Cause Analysis

**Confidence:** {int(rca_conf * 100)}%

{incident_data.get("root_cause", "Analysis pending")}

### Causal Chain
{causal_chain_md}

### Blast Radius
**{incident_data.get("blast_radius", "isolated").replace("-", " ").title()}** — {_blast_radius_description(incident_data.get("blast_radius", "isolated"))}

## 🔧 Fix Recommendation

**Summary:** {incident_data.get("fix_summary", "N/A")}
**Complexity:** {incident_data.get("fix_complexity", "unknown")} | **Est. Time:** {incident_data.get("estimated_time", "unknown")}
**Fix Confidence:** {int(fix_conf * 100)}%

### Steps
{fix_steps_md}
{code_section}

## 🛡️ Preventive Measure
{incident_data.get("preventive_measure", "N/A")}

---
*🤖 Diagnosed by AI DevOps Agent | Anomaly: {int(anomaly_conf*100)}% · RCA: {int(rca_conf*100)}% · Fix: {int(fix_conf*100)}%*
"""

        # Determine labels
        labels = ["incident", "ai-diagnosed"]
        severity_label = severity.lower()
        if severity_label in ("critical", "error", "warning"):
            labels.append(severity_label)

        blast = incident_data.get("blast_radius", "isolated")
        if blast == "system-wide":
            labels.append("system-wide")

        # Create issue — ensure labels exist
        existing_labels = [l.name for l in repo.get_labels()]
        for label in labels:
            if label not in existing_labels:
                try:
                    color = {
                        "critical": "d73a4a",
                        "error": "e36209",
                        "warning": "fbca04",
                        "incident": "0075ca",
                        "ai-diagnosed": "7057ff",
                        "system-wide": "b60205",
                    }.get(label, "ededed")
                    repo.create_label(name=label, color=color)
                except GithubException:
                    pass  # Label might already exist due to race

        issue = repo.create_issue(
            title=title,
            body=body,
            labels=labels,
        )

        logger.info(f"[github] Issue created: {issue.html_url}")
        return issue.html_url

    except GithubException as e:
        logger.error(f"[github] Issue creation failed: {e}")
        return None
    except Exception as e:
        logger.error(f"[github] Unexpected error: {e}", exc_info=True)
        return None


async def create_fix_pr(incident_data: dict[str, Any]) -> Optional[str]:
    """
    Create a fix pull request for trivial fixes with code snippets.

    Creates a new branch, adds/updates a fix file, and opens a PR
    referencing the incident.

    Args:
        incident_data: Combined incident data from all agents.

    Returns:
        GitHub PR URL string, or None on failure.
    """
    try:
        _, repo = _get_github_client()

        incident_id = incident_data.get("incident_id", "unknown")
        short_id = incident_id[:8] if incident_id else "unknown"
        branch_name = f"fix/incident-{short_id}"
        code_snippet = incident_data.get("fix_code_snippet") or incident_data.get("code_snippet", "")

        if not code_snippet:
            logger.info("[github] No code snippet — skipping PR creation")
            return None

        # Get default branch
        default_branch = repo.default_branch
        base_ref = repo.get_git_ref(f"heads/{default_branch}")
        base_sha = base_ref.object.sha

        # Create branch
        try:
            repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=base_sha,
            )
        except GithubException:
            # Branch might already exist
            pass

        # Create/update fix file
        service = incident_data.get("affected_service", "unknown")
        error_type = incident_data.get("error_type", "fix")
        file_path = f"fixes/{service}/{error_type.lower().replace(' ', '_')}_fix.py"

        file_content = f"""# Auto-generated fix for incident {incident_id}
# Error Type: {error_type}
# Service: {service}
# Generated by AI DevOps Agent
#
# Review carefully before merging.

{code_snippet}
"""
        try:
            repo.create_file(
                path=file_path,
                message=f"fix: {incident_data.get('fix_summary', 'Auto-fix for incident')}",
                content=file_content,
                branch=branch_name,
            )
        except GithubException:
            # File might already exist, try update
            try:
                existing = repo.get_contents(file_path, ref=branch_name)
                repo.update_file(
                    path=file_path,
                    message=f"fix: update fix for incident {short_id}",
                    content=file_content,
                    sha=existing.sha,
                    branch=branch_name,
                )
            except GithubException:
                pass

        # Create PR
        pr_body = f"""## 🔧 Auto-Generated Fix

**Incident:** {incident_id}
**Error Type:** {error_type}
**Service:** {service}
**Complexity:** {incident_data.get("fix_complexity", "trivial")}

### Fix Summary
{incident_data.get("fix_summary", "N/A")}

### Root Cause
{incident_data.get("root_cause", "N/A")}

### Changes
This PR adds a fix file generated by the AI DevOps Agent.
**Review the code carefully before merging.**

---
*🤖 Generated by AI DevOps Agent | Fix Confidence: {int(incident_data.get("fix_confidence", 0) * 100)}%*
"""

        pr = repo.create_pull(
            title=f"fix: [{incident_data.get('severity', 'error').upper()}] {error_type} in {service}",
            body=pr_body,
            head=branch_name,
            base=default_branch,
        )

        logger.info(f"[github] PR created: {pr.html_url}")
        return pr.html_url

    except GithubException as e:
        logger.error(f"[github] PR creation failed: {e}")
        return None
    except Exception as e:
        logger.error(f"[github] Unexpected error during PR creation: {e}", exc_info=True)
        return None


def _blast_radius_description(blast_radius: str) -> str:
    """Human-readable blast radius description."""
    return {
        "isolated": "Single service or component affected",
        "partial": "Multiple services or a critical subsystem affected",
        "system-wide": "Entire platform or user-facing services affected",
    }.get(blast_radius, "Unknown impact scope")
