from mcp.server.fastmcp import FastMCP

from jira_plus_mcp.settings import Settings
from jira_plus_mcp.tools.read import register_read_tools
from jira_plus_mcp.tools.write import register_write_tools


def register_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register tools by mode. Write tools are not registered when read-only, so the model never sees them."""
    register_read_tools(mcp, settings)
    if not settings.jira_mcp_read_only:
        register_write_tools(mcp, settings)
