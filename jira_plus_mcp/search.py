from typing import Any

from jira_plus_mcp.client import get_client
from jira_plus_mcp.settings import Deployment, Settings


def search_page(settings: Settings, jql: str, fields: list[str], limit: int) -> list[dict[str, Any]]:
    """Fetch at most `limit + 1` issues in a single request.

    python-jira-plus pages until the instance is exhausted on Cloud and cannot report truncation on-premise,
    so the first page is requested directly. The extra row lets the caller tell whether more matched.
    """
    jira = get_client().jira_client
    cloud = settings.jira_deployment is Deployment.CLOUD
    page = (
        jira.enhanced_search_issues(jql_str=jql, maxResults=limit + 1, fields=fields, json_result=True)
        if cloud
        else jira.search_issues(jql_str=jql, startAt=0, maxResults=limit + 1, fields=fields, json_result=True)
    )
    return page.get("issues", [])
