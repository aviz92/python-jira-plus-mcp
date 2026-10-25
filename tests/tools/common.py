from jira_plus_mcp.settings import Settings

CREDENTIALS = {"jira_base_url": "https://acme.atlassian.net", "jira_user_name": "u", "jira_token": "t"}
WRITABLE = {"jira_mcp_read_only": False}


def make_settings(**overrides: object) -> Settings:
    return Settings(**(CREDENTIALS | overrides))
