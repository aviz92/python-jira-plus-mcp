from functools import lru_cache

from python_jira_plus import JiraCloud, JiraOnPremise
from python_jira_plus.jira_base import JiraBase

from jira_plus_mcp.settings import Deployment, Settings, get_settings


def build_client(settings: Settings) -> JiraBase:
    """The library parses the URL scheme and checks credentials per auth mode, raising ValueError on a gap."""
    common = {
        "base_url": settings.jira_base_url,
        "jira_username": settings.jira_user_name,
        "jira_token": settings.jira_token.get_secret_value(),
        "verify_ssl": settings.jira_verify_ssl,
        "raise_on_error": True,
    }
    if settings.jira_deployment is Deployment.CLOUD:
        return JiraCloud(**common)
    return JiraOnPremise(sso=settings.jira_sso, **common)


@lru_cache(maxsize=1)
def get_client() -> JiraBase:
    """Connect on first tool call, not at server start, so a bad credential doesn't kill the server."""
    return build_client(get_settings())
