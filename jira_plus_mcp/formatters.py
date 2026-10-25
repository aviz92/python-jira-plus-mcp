"""Shape tool results for a model: plain values instead of nested Jira objects. Jira logic lives in python-jira-plus."""

from typing import Any

from jira_plus_mcp.models import IssueDetail, IssueSummary

ALLOWED_VALUE_KEYS = ("id", "key", "name", "value")


def _get(obj: Any, key: str = "name") -> Any:
    return obj.get(key) if isinstance(obj, dict) else None


def format_summary(raw: dict[str, Any]) -> IssueSummary:
    """Flatten a raw issue into plain values: names instead of nested objects with URLs and ids."""
    fields = raw.get("fields") or {}
    return IssueSummary(
        key=raw["key"],
        summary=fields.get("summary"),
        status=_get(fields.get("status")),
        issue_type=_get(fields.get("issuetype")),
        priority=_get(fields.get("priority")),
        assignee=_get(fields.get("assignee"), "displayName"),
        updated=fields.get("updated"),
    )


def format_detail(raw: dict[str, Any]) -> IssueDetail:
    fields = raw.get("fields") or {}
    return IssueDetail(
        **format_summary(raw).model_dump(),
        project=_get(fields.get("project"), "key"),
        reporter=_get(fields.get("reporter"), "displayName"),
        created=fields.get("created"),
        labels=fields.get("labels") or [],
        resolution=_get(fields.get("resolution")),
        parent=_get(fields.get("parent"), "key"),
        description=fields.get("description"),
    )


def format_allowed_values(allowed: list[Any] | None) -> list[dict[str, Any]]:
    """Keep only the identifying keys of each value (drops `self` URLs, icons and the like)."""
    return [
        {k: v[k] for k in ALLOWED_VALUE_KEYS if k in v} if isinstance(v, dict) else {"value": v} for v in allowed or []
    ]
