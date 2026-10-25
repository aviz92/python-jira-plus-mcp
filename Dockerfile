FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock README.md ./
COPY jira_plus_mcp/ ./jira_plus_mcp/
RUN uv sync --frozen --no-dev

# stdio by default; set JIRA_MCP_TRANSPORT=streamable-http to serve over HTTP
CMD ["uv", "run", "--no-sync", "python-jira-plus-mcp"]
