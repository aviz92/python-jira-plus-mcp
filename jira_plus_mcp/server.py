from mcp.server.fastmcp import FastMCP

from jira_plus_mcp.settings import Settings, get_settings
from jira_plus_mcp.tools import register_tools


def create_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or get_settings()
    mcp = FastMCP(name="jira-plus")
    register_tools(mcp, settings)
    return mcp
