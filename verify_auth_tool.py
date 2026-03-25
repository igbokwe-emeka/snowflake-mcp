import asyncio
import os
import sys
from unittest.mock import MagicMock
from dotenv import load_dotenv
from google.adk.tools import ToolContext

# Load env variables
load_dotenv()

# Add agent directory to path
sys.path.insert(0, os.path.join(os.getcwd(), 'agent'))

from snowflake_tools import check_auth_status, AUTH_ID

async def test_auth_status_scenarios():
    from snowflake_tools import get_mcp_server_url
    mcp_url = get_mcp_server_url()
    print(f"Testing Auth ID: {AUTH_ID}")
    print(f"Loaded MCP_SERVER_URL: {mcp_url}")
    
    # helper to create mock context
    def create_mock_context(state):
        ctx = MagicMock()
        ctx.state = state
        return ctx

    # 1. Scenario: No Token
    context_empty = create_mock_context({})
    result_empty = await check_auth_status(tool_context=context_empty)
    print("\nScenario 1: Empty Session State")
    print(f"Status: {result_empty['status']}")
    print(f"Message: {result_empty['message']}")
    
    # If DEV_TOKEN is in .env, status will be READY. 
    # Let's adjust expectation based on environment.
    expected_status = "READY" if os.getenv("DEV_TOKEN") else "AUTH_REQUIRED"
    assert result_empty['status'] == expected_status
    
    # 2. Scenario: Dev Token
    context_dev = create_mock_context({"dev:token": "mock-dev-token"})
    result_dev = await check_auth_status(tool_context=context_dev)
    print("\nScenario 2: Dev Token Present")
    print(f"Status: {result_dev['status']}")
    print(f"Message: {result_dev['message']}")
    assert result_dev['status'] == "READY"
    assert result_dev['session_state']['is_dev_token_present'] is True
    
    # 3. Scenario: Production Token (temp:{AUTH_ID})
    temp_key = f"temp:{AUTH_ID}"
    context_prod = create_mock_context({temp_key: "mock-prod-token"})
    result_prod = await check_auth_status(tool_context=context_prod)
    print(f"\nScenario 3: Production Token Present (key: {temp_key})")
    print(f"Status: {result_prod['status']}")
    print(f"Message: {result_prod['message']}")
    assert result_prod['status'] == "READY"
    assert result_prod['session_state']['is_prod_token_present'] is True
    
    print("\nAll auth status verification scenarios passed!")

if __name__ == "__main__":
    asyncio.run(test_auth_status_scenarios())
