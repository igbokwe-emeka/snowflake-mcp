"""
Custom MCP tool wrapper that supports per-user authentication.

This module provides a custom tool implementation that wraps MCP server calls
with per-user authentication tokens from the session state.
"""
import logging
import os
import json
import base64
from typing import Any, Dict, Optional, List
import httpx
from google.adk.tools import FunctionTool, ToolContext

logger = logging.getLogger(__name__)

# Gemini Enterprise OAuth configuration
AUTH_ID = os.getenv("AUTH_ID", "snowflake-oauth-v6")

# MCP tool names
_MCP_SQL_TOOL = "SQL_Execution_Tool"
_MCP_SEARCH_TOOL = "Support_Tickets_Cortex_Search"

# Local dev/testing only
DEV_TOKEN = os.getenv("DEV_TOKEN")


def get_mcp_server_url() -> str:
    """Helper to get MCP server URL, ensuring it is set when needed."""
    url = os.getenv("MCP_SERVER_URL")
    if not url:
        logger.error("MCP_SERVER_URL environment variable is MISSING. Check your .env or cloud config.")
        return ""
    return url


def get_user_token(tool_context: ToolContext) -> Optional[str]:
    """
    Retrieves the user's delegated OAuth token from the session state.

    In production (Gemini Enterprise), the token is automatically injected
    into session state with key: temp:{AUTH_ID}

    In local/Antigravity testing, falls back to:
    1. Session state key 'dev:token' (set via set_test_token tool)
    2. DEV_TOKEN environment variable
    """
    logger.debug(f"Extracting token for AUTH_ID: {AUTH_ID}")

    # Try to extract keys to see what Gemini is actually passing
    try:
        available_keys = list(tool_context.state.keys()) if hasattr(tool_context.state, "keys") else str(tool_context.state)
        logger.debug(f"Available state keys/data: {available_keys}")
    except Exception as e:
        logger.debug(f"Could not parse state keys: {e}")

    # The Google ADK stores the actual dictionary inside the _value attribute of the State object
    state_dict = getattr(tool_context.state, "_value", {})

    # Production: Gemini Enterprise injects token here
    session_key = AUTH_ID
    token = state_dict.get(session_key)
    if token:
        safe_token = f"{token[:15]}...{token[-5:]}" if isinstance(token, str) and len(token) > 20 else "***"
        logger.debug(f"Using production token from session state (key: {session_key}). Preview: {safe_token}")
        return token

    # Local testing: check session state (set via set_test_token tool)
    token = state_dict.get("dev:token")
    if token:
        logger.info("Using dev token from session state (local testing mode)")
        return token

    # Local testing: fall back to environment variable
    if DEV_TOKEN:
        logger.info("Using DEV_TOKEN from environment (local testing mode)")
        return DEV_TOKEN

    logger.warning(f"No user token found. Expected key: {session_key}")
    logger.debug("Ensure Gemini Enterprise is configured to pass the OAuth token.")
    return None


async def set_test_token(token: str, tool_context: ToolContext = None) -> dict:
    """
    [LOCAL TESTING ONLY] Inject a Snowflake OAuth token into the current session.

    Use this in Antigravity to simulate the token that Gemini Enterprise
    would normally inject automatically.

    Args:
        token: Your Snowflake OAuth access token
        tool_context: ADK tool context (injected automatically)

    Returns:
        Confirmation message
    """
    tool_context.state["dev:token"] = token
    logger.info("Test token set in session state")
    return {"status": "ok", "message": "Token set for this session. You can now query Snowflake."}


async def call_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """
    Call an MCP server tool with per-user authentication via Gemini Enterprise identity propagation.
    
    Args:
        tool_name: Name of the MCP tool to call
        arguments: Arguments to pass to the tool
        tool_context: ADK tool context containing session state with user's OAuth token
        
    Returns:
        Tool execution result
        
    Raises:
        ValueError: If MCP server URL is not configured
    """
    mcp_url = get_mcp_server_url()
    if not mcp_url:
        raise ValueError("MCP_SERVER_URL environment variable not set. Please configure it in your environment.")
    
    # Get user-specific token from Gemini Enterprise session state
    user_token = get_user_token(tool_context)
    if not user_token:
        return {
            "status": "error",
            "error": "User authentication required. Please authenticate via Gemini Enterprise.",
            "error_code": "AUTH_REQUIRED",
            "details": f"Expected token in session state at key: {AUTH_ID}"
        }
    
    # The user's token IS the credential for the MCP server.
    # Gemini Enterprise issues this token via OAuth; the MCP server validates it
    # against Snowflake's External OAuth Security Integration and runs queries
    # as that specific user — no shared service account involved.
    safe_header_token = f"{user_token[:15]}...{user_token[-5:]}" if isinstance(user_token, str) and len(user_token) > 20 else "***"
    logger.debug(f"Preparing to call MCP tool '{tool_name}' with Authorization: Bearer {safe_header_token}")
    
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json"
    }
    
    # Prepare MCP tool call request
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                mcp_url,
                json=mcp_request,
                headers=headers
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Handle MCP error responses
            if "error" in result:
                return {
                    "status": "error",
                    "error": result["error"].get("message", "Unknown MCP error"),
                    "error_code": result["error"].get("code", "UNKNOWN")
                }
            
            # Return successful result
            return {
                "status": "success",
                "data": result.get("result", {})
            }
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error calling MCP tool {tool_name}: {e}")
        return {
            "status": "error",
            "error": f"HTTP {e.response.status_code}: {e.response.text}",
            "error_code": "HTTP_ERROR"
        }
    except Exception as e:
        logger.error(f"Error calling MCP tool {tool_name}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "error_code": "UNKNOWN_ERROR"
        }


# Define specific Snowflake tools
async def list_tables(
    schema: Optional[str] = None,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    List tables in the Snowflake database.
    
    Args:
        schema: Optional schema name to filter tables
        tool_context: ADK tool context (injected automatically)
        
    Returns:
        List of tables with their metadata
    """
    sql = "SHOW TABLES"
    if schema:
        sql += f" IN SCHEMA {schema}"
        
    return await call_mcp_tool(_MCP_SQL_TOOL, {"sql": sql}, tool_context)


async def describe_table(
    table_name: str,
    schema: Optional[str] = None,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Describe the structure of a Snowflake table.
    
    Args:
        table_name: Name of the table to describe
        schema: Optional schema name
        tool_context: ADK tool context (injected automatically)
        
    Returns:
        Table schema information including columns and types
    """
    full_table_name = table_name
    if schema:
        full_table_name = f"{schema}.{table_name}"
        
    sql = f"DESCRIBE TABLE {full_table_name}"
    return await call_mcp_tool(_MCP_SQL_TOOL, {"sql": sql}, tool_context)


async def execute_query(
    query: str,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Execute a SQL query on Snowflake.
    
    Args:
        query: SQL query to execute
        tool_context: ADK tool context (injected automatically)
        
    Returns:
        Query results
    """
    return await call_mcp_tool(_MCP_SQL_TOOL, {"sql": query}, tool_context)


async def search_support_tickets(
    query: str,
    limit: int = 10,
    filter: Optional[str] = None,
    columns: Optional[List[str]] = None,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Search unstructured support ticket data using hybrid keyword and vector (semantic) search.

    Uses Snowflake Cortex Search, which combines BM25 keyword matching with
    vector embeddings to find the most relevant support tickets for a query.

    Args:
        query: Natural language search query, e.g. "login errors after password reset"
        limit: Maximum number of results to return (default 10)
        filter: Optional JSON string representing the filter object.
                Example: '{"@eq": {"status": "open"}}'
                Example: '{"@and": [{"@gte": {"created_date": "2024-01-01"}}, {"@eq": {"priority": "high"}}]}'
        columns: Optional list of columns to return, e.g. ["ticket_id", "subject", "body", "status"]
                 If not specified, all available columns are returned.
        tool_context: ADK tool context (injected automatically)

    Returns:
        Matching support tickets ranked by relevance
    """
    arguments: Dict[str, Any] = {"query": query, "limit": limit}
    
    if filter:
        try:
            # Parse the JSON string into a dictionary
            filter_dict = json.loads(filter)
            arguments["filter"] = filter_dict
        except json.JSONDecodeError:
            return {
                "status": "error",
                "error": "Invalid JSON format for filter parameter",
                "error_code": "INVALID_FILTER_JSON"
            }
            
    if columns:
        arguments["columns"] = columns

    return await call_mcp_tool(_MCP_SEARCH_TOOL, arguments, tool_context)


async def check_auth_status(
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    [DIAGNOSTIC] Check the status of Snowflake authentication in the current session.

    This tool helps validate that Gemini Enterprise is correctly passing its
    authentication token to the agent. It checks the presence of tokens in
    session state but never returns the actual token values.

    Args:
        tool_context: ADK tool context (injected automatically)

    Returns:
        Authentication status report
    """
    session_key = AUTH_ID
    
    # The ADK stores the actual dictionary inside the _value attribute
    state_dict = getattr(tool_context.state, "_value", {})
    
    token = state_dict.get(session_key) or state_dict.get("dev:token") or DEV_TOKEN
    has_prod_token = bool(state_dict.get(session_key))
    has_dev_token = bool(state_dict.get("dev:token"))
    
    status = "READY" if token else "AUTH_REQUIRED"
    available_keys = list(state_dict.keys()) if isinstance(state_dict, dict) else str(type(state_dict))

    jwt_payload = None
    if token and isinstance(token, str) and token.count('.') == 2:
        try:
            # A JWT is three parts separated by dots. The middle part is the payload JSON.
            payload_b64 = token.split('.')[1]
            # Add padding if needed
            payload_b64 += '=' * (-len(payload_b64) % 4)
            jwt_payload_bytes = base64.urlsafe_b64decode(payload_b64)
            jwt_payload = json.loads(jwt_payload_bytes)
        except Exception as e:
            jwt_payload = f"Failed to decode token payload: {str(e)}"

    return {
        "status": status,
        "config": {
            "auth_id": AUTH_ID,
            "expected_session_key": session_key,
            "mcp_server_url": get_mcp_server_url()
        },
        "session_state": {
            "is_prod_token_present": has_prod_token,
            "is_dev_token_present": has_dev_token,
            "is_env_dev_token_present": bool(DEV_TOKEN),
            "available_keys": available_keys,
            "token_claims": jwt_payload
        },
        "message": "Authentication is correctly configured." if status == "READY" else "Missing user token. Please authenticate via Gemini Enterprise."
    }


# Create FunctionTool instances
list_tables_tool = FunctionTool(func=list_tables)
describe_table_tool = FunctionTool(func=describe_table)
execute_query_tool = FunctionTool(func=execute_query)
set_test_token_tool = FunctionTool(func=set_test_token)
search_support_tickets_tool = FunctionTool(func=search_support_tickets)

# Export all tools
SNOWFLAKE_TOOLS = [
    list_tables_tool,
    describe_table_tool,
    execute_query_tool,
    search_support_tickets_tool,
    set_test_token_tool,
    FunctionTool(func=check_auth_status),
]
