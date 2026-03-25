# Snowflake MCP Agent

This agent uses the Model Context Protocol (MCP) to connect to a Snowflake database and perform operations like listing tables and running queries.

**✨ Gemini Enterprise Identity Propagation**: This agent integrates with Gemini Enterprise to automatically use each user's OAuth credentials for Snowflake access. No manual token management required. See [AUTHENTICATION.md](AUTHENTICATION.md) for setup details.


It consists of two components:
1.  **MCP Server**: A Docker container running a FastMCP server that wraps Snowflake operations.
2.  **Agent**: A Google ADK Agent that connects to the MCP server to answer user queries.

## Prerequisites

- Docker and Docker Compose
- A Snowflake account
- A Google Cloud Project with Gemini API access (or other supported LLM)

## Setup

1.  **Clone the repository** (if you haven't already).
2.  **Navigate to the agent directory**:
    ```bash
    cd python/agents/snowflake-mcp-agent
    ```
3.  **Configure Environment Variables**:
    Copy `.env.example` to `.env` and fill in your credentials.
    ```bash
    cp .env.example .env
    ```
    You will need:
    - `GOOGLE_API_KEY`: Your Gemini API key.
    - `MCP_SERVER_URL`: The URL of your Snowflake Managed MCP Server.
    - `MCP_SERVER_TOKEN`: Access token for the MCP Server.

## Running the Agent

Start the agent using Docker Compose:

```bash
docker-compose up --build
```

This will start the Agent on port `10000`.

## Interacting with the Agent

You can interact with the agent using the Agent Engine or by sending requests involving Snowflake data.

Example queries:
- "List all tables in the PUBLIC schema."
- "Show me the columns in the 'customers' table."
- "Run a query to count the number of orders in the last month."

## Architecture

- **`agent/`**: Contains the ADK agent definition (`agent.py`) which connects to the remote Snowflake Managed MCP server via SSE (Server-Sent Events).

