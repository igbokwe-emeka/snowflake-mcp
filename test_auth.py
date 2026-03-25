"""
Example script demonstrating per-user authentication with the Snowflake agent.

This script shows how to:
1. Create sessions for multiple users
2. Set user-specific tokens
3. Run queries with proper user attribution
"""
import asyncio
import os
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.genai import types

load_dotenv()

# Import the agent
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agent'))
from agent import root_agent


async def test_multi_user_auth():
    """Test the agent with multiple users, each with their own token."""
    
    # Initialize services
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    
    runner = Runner(
        app_name='snowflake_agent',
        agent=root_agent,
        session_service=session_service,
        artifact_service=artifact_service
    )
    
    # Simulate two different users with different tokens
    users = [
        {
            'user_id': 'alice@example.com',
            'token': 'alice_snowflake_token_123',  # Replace with real token
            'query': 'List all tables in the database'
        },
        {
            'user_id': 'bob@example.com',
            'token': 'bob_snowflake_token_456',  # Replace with real token
            'query': 'Show me the schema for the customers table'
        }
    ]
    
    for user in users:
        print(f"\n{'='*60}")
        print(f"Testing user: {user['user_id']}")
        print(f"{'='*60}\n")
        
        # Create session with user-specific token
        session = await session_service.create_session(
            app_name='snowflake_agent',
            user_id=user['user_id'],
            state={
                'user_snowflake_token': user['token']
            }
        )
        
        print(f"Session created: {session.id}")
        print(f"User query: {user['query']}\n")
        
        # Run the agent
        content = types.Content(
            role='user',
            parts=[types.Part(text=user['query'])]
        )
        
        try:
            async for event in runner.run_async(
                session_id=session.id,
                user_id=user['user_id'],
                new_message=content
            ):
                # Print agent responses
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            print(f"Agent: {part.text}")
                        elif part.function_call:
                            print(f"Tool call: {part.function_call.name}")
                        elif part.function_response:
                            print(f"Tool response: {part.function_response.name}")
        except Exception as e:
            print(f"Error: {e}")
        
        print(f"\n{'='*60}\n")


async def test_missing_token():
    """Test what happens when a user doesn't have a token."""
    
    print(f"\n{'='*60}")
    print("Testing user without token")
    print(f"{'='*60}\n")
    
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    
    runner = Runner(
        app_name='snowflake_agent',
        agent=root_agent,
        session_service=session_service,
        artifact_service=artifact_service
    )
    
    # Create session WITHOUT a token
    session = await session_service.create_session(
        app_name='snowflake_agent',
        user_id='charlie@example.com',
        state={}  # No token!
    )
    
    content = types.Content(
        role='user',
        parts=[types.Part(text='List all tables')]
    )
    
    try:
        async for event in runner.run_async(
            session_id=session.id,
            user_id='charlie@example.com',
            new_message=content
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(f"Agent: {part.text}")
                    elif part.function_response:
                        # Should see AUTH_REQUIRED error
                        print(f"Tool response: {part.function_response.response}")
    except Exception as e:
        print(f"Error: {e}")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    print("Snowflake Agent - Per-User Authentication Test")
    print("=" * 60)
    
    # Run tests
    asyncio.run(test_multi_user_auth())
    asyncio.run(test_missing_token())
    
    print("\nTests completed!")
