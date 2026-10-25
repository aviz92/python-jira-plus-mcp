from functools import lru_cache

from python_jira_plus import JiraCloud, JiraOnPremise, UrlScheme
from python_jira_plus.jira_base import JiraBase

from jira_plus_mcp.settings import Deployment, Settings, get_settings


def _split_scheme(base_url: str) -> tuple[str, UrlScheme]:
    """The library expects the host without a scheme and takes the scheme separately."""
    if base_url.startswith("http://"):
        return base_url.removeprefix("http://").rstrip("/"), UrlScheme.HTTP
    return base_url.removeprefix("https://").rstrip("/"), UrlScheme.HTTPS


def build_client(settings: Settings) -> JiraBase:
    host, scheme = _split_scheme(settings.jira_base_url)
    common = {
        "base_url": host,
        "jira_username": settings.jira_user_name,
        "jira_token": settings.jira_token.get_secret_value(),
        "verify_ssl": settings.jira_verify_ssl,
        "url_scheme": scheme,
    }
    if settings.jira_deployment is Deployment.CLOUD:
        return JiraCloud(**common)
    return JiraOnPremise(sso=settings.jira_sso, **common)


@lru_cache(maxsize=1)
def get_client() -> JiraBase:
    """Connect on first tool call, not at server start, so a bad credential doesn't kill the server."""
    return build_client(get_settings())
