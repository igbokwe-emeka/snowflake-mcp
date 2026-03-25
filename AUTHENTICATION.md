# Gemini Enterprise Identity Propagation Guide

## Overview

This agent uses **Gemini Enterprise Identity Propagation** to ensure each user accesses Snowflake with their own credentials. Gemini Enterprise acts as the OAuth orchestrator, managing user authentication and token delegation.

## Architecture

```
User → Gemini Enterprise (OAuth) → ADK Agent → Snowflake MCP Server → Snowflake
                                        ↓
                                  temp:{AUTH_ID} token
```

1. **User Login**: User authenticates via Gemini Enterprise (using Workload Identity Federation or SSO)
2. **OAuth Flow**: Gemini Enterprise triggers OAuth flow against your identity provider (e.g., Azure AD/Entra ID)
3. **Token Delegation**: Gemini Enterprise stores the user's access token in session state with key `temp:{AUTH_ID}`
4. **Agent Access**: ADK agent retrieves token from `ToolContext.state`
5. **Snowflake Auth**: Token is passed to Snowflake MCP server, which validates it against External OAuth Security Integration

## Setup Steps

### 1. Configure Snowflake External OAuth Integration

Create an External OAuth Security Integration in Snowflake to trust tokens from your identity provider:

```sql
CREATE SECURITY INTEGRATION snowflake_oauth
  TYPE = EXTERNAL_OAUTH
  ENABLED = TRUE
  EXTERNAL_OAUTH_TYPE = AZURE  -- or OKTA, CUSTOM, etc.
  EXTERNAL_OAUTH_ISSUER = 'https://login.microsoftonline.com/{tenant-id}/v2.0'
  EXTERNAL_OAUTH_JWS_KEYS_URL = 'https://login.microsoftonline.com/{tenant-id}/discovery/v2.0/keys'
  EXTERNAL_OAUTH_AUDIENCE_LIST = ('https://analysis.windows.net/powerbi/connector/Snowflake')
  EXTERNAL_OAUTH_TOKEN_USER_MAPPING_CLAIM = 'upn'  -- or 'email'
  EXTERNAL_OAUTH_SNOWFLAKE_USER_MAPPING_ATTRIBUTE = 'LOGIN_NAME'
  EXTERNAL_OAUTH_ANY_ROLE_MODE = 'ENABLE';
```

**Key Parameters:**

- `EXTERNAL_OAUTH_ISSUER`: Your identity provider's issuer URL
- `EXTERNAL_OAUTH_JWS_KEYS_URL`: URL to fetch public keys for token validation
- `EXTERNAL_OAUTH_AUDIENCE_LIST`: Expected audience claim in the JWT
- `EXTERNAL_OAUTH_TOKEN_USER_MAPPING_CLAIM`: Claim in JWT that identifies the user (e.g., `email`, `upn`)
- `EXTERNAL_OAUTH_SNOWFLAKE_USER_MAPPING_ATTRIBUTE`: Snowflake user attribute to match against

### 2. Map Snowflake Users

Ensure Snowflake users have a `LOGIN_NAME` that matches the claim in the JWT:

```sql
-- If using email claim
ALTER USER alice@example.com SET LOGIN_NAME = 'alice@example.com';

-- If using UPN claim
ALTER USER alice@example.com SET LOGIN_NAME = 'alice@contoso.com';
```

### 3. Register OAuth Resource in Gemini Enterprise

In the Gemini Enterprise console:

1. **Navigate to your Custom Agent** registration
2. **Add Authorization**:
   - Type: OAuth authorization resource
   - Authorization Endpoint: Your identity provider's auth endpoint
   - Token Endpoint: Your identity provider's token endpoint
   - Scopes:
     - `session:role-any` (for Snowflake)
     - `offline_access` (for token refresh)
3. **Note the AUTH_ID**: Gemini Enterprise generates a unique AUTH_ID for this resource
4. **Link to Agent**: Attach this authorization resource to your agent

### 4. Configure Agent Environment

Set the `AUTH_ID` in your `.env` file:

```bash
AUTH_ID=your-auth-id-from-gemini-enterprise
MCP_SERVER_URL=https://your-snowflake-mcp-server-url
GOOGLE_API_KEY=your-google-api-key
```

## How It Works

### Token Retrieval

The agent automatically retrieves the user's token from session state:

```python
def get_user_token(tool_context: ToolContext) -> Optional[str]:
    """Retrieves the user's delegated OAuth token from the session state."""
    token_key = f"temp:{AUTH_ID}"
    return tool_context.state.get(token_key)
```

### Token Usage

The token is passed to the Snowflake MCP server in the Authorization header:

```python
headers = {
    "Authorization": f"Bearer {user_token}",
    "Content-Type": "application/json"
}
```

### Snowflake Validation

The Snowflake MCP server validates the token against the External OAuth Security Integration and executes queries with the user's permissions.

## Security Benefits

1. **No Shared Secrets**: Agent never sees a "master" Snowflake password
2. **User-Level RBAC**: Snowflake applies permissions and masking policies for each individual user
3. **Session Isolation**: Each user session gets a dedicated, sandboxed agent instance
4. **Audit Trail**: Snowflake logs show actual user attribution
5. **Token Refresh**: Gemini Enterprise automatically refreshes tokens using `offline_access` scope

## Troubleshooting

### Token Not Found

If you see `AUTH_REQUIRED` error:

- Verify `AUTH_ID` matches the ID from Gemini Enterprise
- Ensure user has completed OAuth flow in Gemini Enterprise
- Check that authorization resource is linked to the agent

### Snowflake Authentication Failed

If Snowflake rejects the token:

- Verify External OAuth Security Integration is enabled
- Check `EXTERNAL_OAUTH_ISSUER` matches your identity provider
- Ensure user's `LOGIN_NAME` matches the JWT claim
- Validate token claims using jwt.io

### Token Expired

Gemini Enterprise automatically refreshes tokens if:

- `offline_access` scope is included
- Refresh token is still valid
- User re-authenticates if refresh fails

## Example: Azure AD Configuration

### Snowflake Integration

```sql
CREATE SECURITY INTEGRATION azure_ad_oauth
  TYPE = EXTERNAL_OAUTH
  ENABLED = TRUE
  EXTERNAL_OAUTH_TYPE = AZURE
  EXTERNAL_OAUTH_ISSUER = 'https://login.microsoftonline.com/{tenant-id}/v2.0'
  EXTERNAL_OAUTH_JWS_KEYS_URL = 'https://login.microsoftonline.com/{tenant-id}/discovery/v2.0/keys'
  EXTERNAL_OAUTH_AUDIENCE_LIST = ('https://analysis.windows.net/powerbi/connector/Snowflake')
  EXTERNAL_OAUTH_TOKEN_USER_MAPPING_CLAIM = 'upn'
  EXTERNAL_OAUTH_SNOWFLAKE_USER_MAPPING_ATTRIBUTE = 'LOGIN_NAME'
  EXTERNAL_OAUTH_ANY_ROLE_MODE = 'ENABLE';
```

### Gemini Enterprise OAuth Resource

- **Authorization Endpoint**: `https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/authorize`
- **Token Endpoint**: `https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/token`
- **Scopes**: `session:role-any`, `offline_access`

## Validation & Tracking

To verify that Gemini Enterprise is correctly propagating the `AUTH_ID` and user tokens, you can use the built-in diagnostic tools.

### 1. Using the Diagnostic Tool

You can ask the agent to run an authentication check at any time:
> "Run the auth status check" or "Check my authentication status"

The agent will return a report containing:

- **Status**: `READY` or `AUTH_REQUIRED`.
- **Config**: Shows the configured `AUTH_ID` and the session key it expects.
- **Session State**: Lists all "auth-related" keys found in the current session (e.g., `temp:snowflake-oauth-v2`).
- **Validation**: Confirms if a production or development token is present.

### 2. Checking Logs

The agent logs detailed (but secure) information about token retrieval:

#### Agent Engine / Cloud Run Logs

Look for these patterns in your logs:

- `Using production token from session state (key: temp:...)`: Success! Gemini Enterprise passed the token correctly.
- `No user token found. Expected key: temp:...`: The `AUTH_ID` might be misconfigured, or the user hasn't completed the OAuth flow.
- `Available session state keys: [...]`: In case of failure, this log (at DEBUG level) shows what *was* passed, helping identify if Gemini Enterprise is using a different key.

#### Snowsight Logs

To verify Snowflake actually received the user's identity:

```sql
SELECT 
    query_text, 
    user_name, 
    role_name, 
    client_application_id 
FROM TABLE(information_schema.query_history())
ORDER BY start_time DESC;
```

If the propagation is working, `user_name` will reflect the individual user (e.g., `alice@example.com`) rather than a generic service account.

## References

...
