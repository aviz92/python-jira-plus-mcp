from typing import Any, NamedTuple

from jira_plus_mcp.client import get_client
from jira_plus_mcp.settings import Deployment, Settings


class SearchPage(NamedTuple):
    issues: list[dict[str, Any]]
    has_more: bool


def search_page(settings: Settings, jql: str, fields: list[str], limit: int) -> SearchPage:
    """Fetch the first page of at most `limit + 1` issues in a single request.

    python-jira-plus pages until the instance is exhausted on Cloud and cannot report truncation on-premise,
    so the first page is requested directly. `has_more` comes from the API itself (`isLast` on Cloud, `total`
    on-prem), because Cloud can return a short page that is not the last one.
    """
    jira = get_client().jira_client
    if settings.jira_deployment is Deployment.CLOUD:
        page = jira.enhanced_search_issues(jql_str=jql, maxResults=limit + 1, fields=fields, json_result=True)
        has_more = not page.get("isLast", True)
    else:
        page = jira.search_issues(jql_str=jql, startAt=0, maxResults=limit + 1, fields=fields, json_result=True)
        has_more = page.get("total", 0) > limit
    issues = page.get("issues", [])
    return SearchPage(issues=issues, has_more=has_more or len(issues) > limit)
