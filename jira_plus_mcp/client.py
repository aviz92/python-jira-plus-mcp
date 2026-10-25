from collections.abc import Callable
from functools import cache

from python_jira_plus import JiraCloud, JiraOnPremise
from python_jira_plus.jira_base import JiraBase

from jira_plus_mcp.settings import Deployment, Settings


def build_client(settings: Settings) -> JiraBase:
    """The library parses the URL, checks credentials per auth mode and enforces the project allowlist."""
    common = {
        "base_url": settings.jira_base_url,
        "jira_username": settings.jira_user_name,
        "jira_token": settings.jira_token.get_secret_value(),
        "verify_ssl": settings.jira_verify_ssl,
        "raise_on_error": True,
        "allowed_projects": settings.jira_mcp_allowed_projects,
    }
    if settings.jira_deployment is Deployment.CLOUD:
        return JiraCloud(**common)
    return JiraOnPremise(sso=settings.jira_sso, **common)


def client_factory(settings: Settings) -> Callable[[], JiraBase]:
    """A per-server client, bound to that server's settings.

    It connects on the first tool call, not at server start, so a bad credential doesn't kill the server.
    """

    @cache
    def get_client() -> JiraBase:
        return build_client(settings)

    return get_client
