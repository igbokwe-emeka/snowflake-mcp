import os
import asyncio
import httpx
from dotenv import load_dotenv
import json

load_dotenv()

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")
DEV_TOKEN = os.getenv("DEV_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

async def list_tools():
    if not MCP_SERVER_URL:
        print("Error: MCP_SERVER_URL not set")
        return
    
    if not DEV_TOKEN:
        print("Error: DEV_TOKEN not set")
        return

    print(f"Connecting to MCP Server: {MCP_SERVER_URL}")
    print(f"Using Token: {DEV_TOKEN[:10]}...")

    headers = {
        "Authorization": f"Bearer {DEV_TOKEN}",
        "Content-Type": "application/json"
    }

    # JSON-RPC request to list tools
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                MCP_SERVER_URL,
                json=mcp_request,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                print(f"MCP Error: {result['error']}")
            else:
                tools = result.get("result", {}).get("tools", [])
                print(f"\nFound {len(tools)} tools:")
                for tool in tools:
                    print(f"- {tool['name']}: {tool.get('description', 'No description')}")
                    print(f"  Schema: {json.dumps(tool.get('inputSchema', {}), indent=2)}")

    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(list_tools())
