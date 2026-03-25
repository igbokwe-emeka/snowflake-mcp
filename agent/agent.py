# Load environment variables (MUST BE FIRST)
from dotenv import load_dotenv
load_dotenv()

import logging
import os
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from .snowflake_tools import SNOWFLAKE_TOOLS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """
You are a Snowflake assistant. Your goal is to help users query and understand their Snowflake data.
You have access to tools to:
- List and describe tables
- Run SQL queries
- Search support tickets using hybrid keyword and vector (semantic) search

When searching support tickets, use natural language queries. You can filter by fields like
status, priority, or date ranges. Always summarize the most relevant results clearly.

Each user has their own Snowflake credentials. The system will automatically use
the authenticated user's credentials for all database operations.
"""

logger.info("--- Initializing Snowflake Agent... ---")

# Verify MCP server configuration
mcp_url = os.getenv("MCP_SERVER_URL")
if not mcp_url:
    logger.warning("MCP_SERVER_URL not set. Agent may not function correctly without an MCP server.")

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="snowflake_agent",
    description="A helpful assistant for Snowflake database operations with per-user authentication.",
    instruction=SYSTEM_INSTRUCTION,
    tools=SNOWFLAKE_TOOLS,
)

# Convert to A2A app for Agent Engine
a2a_app = to_a2a(root_agent, port=int(os.getenv("PORT", 10000)))

if __name__ == "__main__":
    # This block is for local testing confirmation
    logger.info(f"Agent configured with custom authenticated tools for MCP at {mcp_url}")
