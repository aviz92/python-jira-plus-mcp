from jira_plus_mcp.server import create_server
from jira_plus_mcp.settings import get_settings


def main() -> None:
    """Entry point. stdout is the stdio protocol channel, so nothing may print to it."""
    create_server().run(transport=get_settings().jira_mcp_transport.value)


if __name__ == "__main__":
    main()
