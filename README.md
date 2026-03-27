# Snowflake MCP Agent

An ADK agent that uses the Snowflake Managed MCP Server to answer queries about Snowflake data. It is deployed on **Vertex AI Agent Engine** and registered in **Gemini Enterprise**, where each user's Entra ID OAuth credentials are automatically propagated — no manual token management required.

See [AUTHENTICATION.md](AUTHENTICATION.md) for OAuth setup details.

---

## Architecture

- **Agent Engine (Vertex AI)** — hosts the ADK `LlmAgent` as a Reasoning Engine.
- **Gemini Enterprise** — surfaces the agent to end-users and handles per-user OAuth via a registered authorization resource.
- **Snowflake Managed MCP Server** — the agent calls this over SSE using each user's Entra ID token to query Snowflake.

---

## Prerequisites

- Google Cloud project with Vertex AI and Discovery Engine APIs enabled
- `gcloud` CLI authenticated (`gcloud auth login`)
- Gemini Enterprise Data Store / Engine already provisioned (provides `ENGINE_ID`)
- Azure AD app registration for Snowflake OAuth (provides `CLIENTID`, `TENANTID`, `CLIENT_SECRET`)

---

## Deployment Scripts

All scripts live in [deploy/](deploy/). The real scripts (`*.sh`) are gitignored — copy from the `.example` files and fill in your values.

### Full pipeline (deploy + register)

```bash
export CLIENT_SECRET="<your-azure-ad-client-secret>"
bash deploy/deploy_agent_engine.sh
```

This runs both steps in sequence:

| Step | Script | Action |
|------|--------|--------|
| 1 | `deploy_agent_engine.sh` | Deploys the agent package to Vertex AI Agent Engine |
| 2 | `register_agent.sh` | Queries Agent Engine for the latest Reasoning Engine, then registers it in Gemini Enterprise |

### Registration only (re-register after a new deploy)

```bash
export CLIENT_SECRET="<your-azure-ad-client-secret>"
bash deploy/register_agent.sh
```

`register_agent.sh` automatically fetches the latest Reasoning Engine ID from Agent Engine. To pin a specific version instead:

```bash
export REASONING_ENGINE_ID="<id>"
export CLIENT_SECRET="<your-azure-ad-client-secret>"
bash deploy/register_agent.sh
```

### Configuration

Variables are set at the top of each script. Copy from the `.example` file:

```bash
cp deploy/register_agent.sh.example deploy/register_agent.sh
cp deploy/deploy_agent_engine.sh.example deploy/deploy_agent_engine.sh
```

| Variable | Script | Description |
|---|---|---|
| `PROJECT_NUMBER` | `register_agent.sh` | GCP project number |
| `PROJECT_ID` | both | GCP project ID |
| `LOCATION` | `register_agent.sh` | Discovery Engine region (e.g. `us`) |
| `AUTH_ID` | `register_agent.sh` | Authorization resource name |
| `ENGINE_ID` | `register_agent.sh` | Gemini Enterprise engine ID |
| `TENANTID` / `CLIENTID` | `register_agent.sh` | Azure AD app registration |
| `CLIENT_SECRET` | both | Set via environment — never hardcode |
| `STAGING_BUCKET` | `deploy_agent_engine.sh` | GCS bucket used during ADK deploy |

---

## Configuration

The agent reads runtime configuration from `agent/.agent_engine_config.json`:

```json
{
  "env_vars": {
    "AUTH_ID": "snowflake-oauth-v6",
    "MCP_SERVER_URL": "<snowflake-mcp-server-url>",
    "GOOGLE_API_KEY": "<api-key>",
    "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "true"
  }
}
```

---

## Example Queries

Once registered in Gemini Enterprise, users can ask:

- "List all tables in the PUBLIC schema."
- "Show me the columns in the `customers` table."
- "Count the number of orders placed in the last 30 days."
- "Search support tickets with status open and priority high."
