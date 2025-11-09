# Data Orchestration Agent

Root orchestration agent for data discovery, planning, and product creation using Google's Agent Development Kit (ADK).

## Overview

The Data Orchestration Agent provides a unified interface for working with multiple specialized data agents through three operational modes:

- **Ask Mode**: Discover datasets, generate SQL queries, and analyze BigQuery data
- **Planning Mode**: Create comprehensive Data Product Requirement Prompts (PRPs) through guided conversation
- **Action Mode**: Execute PRPs to build SQL queries and deploy GraphQL APIs

The agent orchestrates five MCP (Model Context Protocol) services:
- Data Discovery Agent
- Query Generation Agent  
- Data Planning Agent
- Data GraphQL Agent
- Apollo MCP Server

## Architecture

```
┌─────────────────────────────────────────┐
│   Data Orchestration Agent (ADK)        │
│   ┌──────────┬───────────┬──────────┐   │
│   │ Ask Mode │  Planning │  Action  │   │
│   │          │    Mode   │   Mode   │   │
│   └──────────┴───────────┴──────────┘   │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┼─────────────────┐
        │         │                 │
   ┌────▼───┐ ┌──▼────┐      ┌─────▼─────┐
   │Discovery│ │Planning│      │Query Gen  │
   │ Agent  │ │ Agent  │      │  Agent    │
   └────────┘ └────────┘      └───────────┘
        │                           │
   ┌────▼────┐                ┌────▼─────┐
   │GraphQL  │                │Apollo    │
   │ Agent   │                │MCP       │
   └─────────┘                └──────────┘
```

## Features

### Ask Mode
The default mode for data exploration and analysis:
- **Dataset Discovery**: Natural language search across BigQuery catalog
- **Schema Inspection**: Detailed table metadata and column information
- **Query Generation**: Convert questions to SQL using intelligent query generation
- **Query Execution**: Run SQL queries directly and view formatted results
- **Query History**: Track, view, and reuse previous queries across sessions
- **Iterative Refinement**: Refine searches with suggested alternatives when results don't match intent

### Planning Mode
Create comprehensive Data Product Requirement Prompts (PRPs):
- **Session Tracking**: Automatic conversation history capture for context
- **Dataset Discovery**: Find and validate source tables for your requirements
- **Intelligent Q&A**: AI-driven question generation to gather complete requirements
- **PRP Generation**: Automated creation of structured requirement documents
- **PRP Refinement**: Iterate on generated PRPs with targeted modifications
- **Context Handoff**: Seamlessly transfer to Action Mode with all planning context preserved

### Action Mode
Execute PRPs to build complete data products:
- **Source Discovery**: Automatically identify source tables from PRP requirements
- **Query Generation**: Generate SQL queries from discovered sources and requirements
- **GraphQL API Creation**: Scaffold complete GraphQL APIs from validated queries
- **Step Iteration**: Refine any workflow step (discovery, queries, or GraphQL)
- **GraphQL Execution**: Run operations against deployed GraphQL APIs

## Installation

### Prerequisites
- Python 3.10 or higher
- Poetry for dependency management
- Access to Google Cloud Platform
- Running MCP services (discovery, query-gen, planning, graphql, apollo)

### Setup

1. **Clone the repository**:
```bash
cd /home/user/git/data-orchestration-agent
```

2. **Install dependencies**:
```bash
poetry install
```

3. **Configure environment variables**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
- `GCP_PROJECT_ID`: Google Cloud project ID
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account key
- `GOOGLE_API_KEY`: Google AI API key for Gemini model
- MCP service URLs (see .env.example)

4. **Run the agent**:

**CopilotKit AG-UI Server (Recommended - for frontend integration):**
```bash
# Run the CopilotKit-powered AG-UI server
python -m data_orchestration_agent.main

# Or with custom settings
python -m data_orchestration_agent.main --host 0.0.0.0 --port 8085 --verbose
```

The server uses the official [CopilotKit SDK](https://docs.copilotkit.ai/adk/quickstart?path=exiting-agent) (`ag-ui-adk` package) and will start on `http://localhost:8085` by default, providing:
- **Full AG-UI Protocol Support**: WebSocket-based bidirectional communication
- **Real-time Streaming**: Server-Sent Events for live agent responses
- **State Synchronization**: Automatic state management between frontend and backend
- **CopilotKit Compatible**: Works seamlessly with CopilotKit React components
- **Standard Implementation**: Uses maintained CopilotKit SDK instead of custom code

**Alternative: ADK Development UI:**
```bash
# For ADK's built-in development interface
poetry run adk web src
```

## Usage

### CopilotKit AG-UI API (Recommended for Frontend Integration)

The server uses the official [CopilotKit SDK](https://docs.copilotkit.ai/adk/quickstart?path=exiting-agent) to expose your ADK agent through the AG-UI protocol. The `ag-ui-adk` package automatically provides all necessary endpoints for frontend integration at `http://localhost:8085` by default.

**What CopilotKit Provides:**
- WebSocket endpoint for bidirectional real-time communication
- HTTP endpoints for chat, state management, and tool execution
- Server-Sent Events for streaming responses
- Automatic state synchronization with AG-UI frontends
- Full compatibility with CopilotKit React components

**Key Benefits:**
- ✅ **Standard Implementation**: Uses official CopilotKit SDK (~80 lines vs 600+ custom code)
- ✅ **Maintained by CopilotKit**: Updates and improvements handled upstream
- ✅ **Better Compatibility**: Guaranteed to work with CopilotKit frontends
- ✅ **Less Complexity**: No manual event conversion or state management code

#### Health Check
```bash
curl http://localhost:8085/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "data-orchestration-agent-copilotkit",
  "transport": "http"
}
```

#### Frontend Integration

The CopilotKit SDK provides all the endpoints needed for frontend integration automatically. For frontend developers:

**Using CopilotKit React:**
```typescript
import { CopilotKit } from "@copilotkit/react-core";

function App() {
  return (
    <CopilotKit runtimeUrl="http://localhost:8085">
      {/* Your app components */}
    </CopilotKit>
  );
}
```

**AG-UI Protocol Endpoints (handled by CopilotKit SDK):**
- WebSocket at `/` for bidirectional communication
- HTTP endpoints for chat, state, and tool execution
- Server-Sent Events for streaming responses
- All protocol details handled automatically

For detailed frontend integration, see:
- [CopilotKit React Documentation](https://docs.copilotkit.ai/)
- [AG-UI Protocol Documentation](https://docs.copilotkit.ai/adk/quickstart?path=exiting-agent)

### ADK REST API

The ADK API server provides a REST API for interacting with the agent. For detailed documentation, visit the [interactive API docs](http://localhost:8000/docs) when the server is running.

**Note:** The AG-UI server (above) is recommended for frontend integration. Use the ADK REST API for direct ADK protocol communication or when using the ADK development UI.

#### List Available Agents
```bash
curl -X GET http://localhost:8000/list-apps
```

**Expected Response:**
```json
["data_orchestration_agent"]
```

#### Create/Update Session
```bash
curl -X POST http://localhost:8000/apps/data_orchestration_agent/users/user_123/sessions/session_abc \
  -H "Content-Type: application/json" \
  -d '{"initial_state": "value"}'
```

**Expected Response:**
```json
{
  "id": "session_abc",
  "appName": "data_orchestration_agent",
  "userId": "user_123",
  "state": {"initial_state": "value"},
  "events": [],
  "lastUpdateTime": 1762648817.7493935
}
```

#### Get Session Details
```bash
curl -X GET http://localhost:8000/apps/data_orchestration_agent/users/user_123/sessions/session_abc
```

**Expected Response:**
```json
{
  "id": "session_abc",
  "appName": "data_orchestration_agent",
  "userId": "user_123",
  "state": {"initial_state": "value"},
  "events": [],
  "lastUpdateTime": 1762648817.7493935
}
```

#### Run Agent (Single Response)
```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "data_orchestration_agent",
    "user_id": "user_123",
    "session_id": "session_abc",
    "new_message": {
      "role": "user",
      "parts": [{"text": "Help me find customer data"}]
    }
  }'
```

**Expected Response:**
Returns an array of events showing the agent's execution flow:
- Transfer to Ask Mode
- Search for datasets matching "customer data"
- Return formatted results with suggested refinements

The response includes:
- Model content with agent responses
- Tool calls (e.g., `search_datasets`, `transfer_to_agent`)
- State changes and artifacts
- Complete conversation history

**Example Response Structure:**
```json
[
  {
    "content": {
      "parts": [{"functionCall": {"name": "transfer_to_agent", "args": {"agent_name": "ask_agent"}}}],
      "role": "model"
    },
    "author": "data_orchestration_agent",
    ...
  },
  {
    "content": {
      "parts": [{"functionCall": {"name": "search_datasets", "args": {"query": "customer data"}}}],
      "role": "model"
    },
    "author": "ask_agent",
    ...
  },
  {
    "content": {
      "parts": [{"text": "# Ask Mode\nI found several datasets..."}],
      "role": "model"
    },
    "author": "ask_agent",
    ...
  }
]
```

#### Run Agent (Streaming)
```bash
curl -X POST http://localhost:8000/run_sse \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "data_orchestration_agent",
    "user_id": "user_123",
    "session_id": "session_abc",
    "new_message": {
      "role": "user",
      "parts": [{"text": "Show me tables related to customer orders"}]
    },
    "streaming": true
  }'
```

**Expected Response:**
Server-Sent Events (SSE) stream with `data:` prefixed JSON events:
```
data: {"content":{"parts":[...],"role":"model"},"author":"root_orchestration_agent",...}

data: {"content":{"parts":[...],"role":"model"},"author":"ask_agent",...}

data: {"content":{"parts":[{"text":"# Ask Mode\n..."}],"role":"model"},...}
```

Each event is delivered as it occurs, enabling real-time streaming responses.

#### Delete Session
```bash
curl -X DELETE http://localhost:8000/apps/data_orchestration_agent/users/user_123/sessions/session_abc
```

**Expected Response:**
```
null
```

Returns empty response with HTTP 204 No Content status on successful deletion.

### Example Workflows

All workflows use the ADK API `/run` or `/run_sse` endpoints with this structure:

```json
{
  "app_name": "root_orchestration_agent",
  "user_id": "user_123",
  "session_id": "session_abc",
  "new_message": {
    "role": "user",
    "parts": [{"text": "your message here"}]
  }
}
```

#### Ask Mode: Discover and Explore Datasets

**User Message:**
```
Show me all tables related to customer orders
```

**What happens:**
- Agent searches BigQuery catalog using natural language
- Returns table names, descriptions, and row counts
- User can follow up asking for specific table schemas

#### Ask Mode: Generate and Execute SQL Queries

**User Message:**
```
How many orders were placed last week?
```

**What happens:**
- Agent discovers relevant tables automatically
- Generates appropriate SQL query
- Executes the query in BigQuery
- Returns formatted results as markdown table

**Query History:**

**User Message:**
```
What queries have I run?
```

Agent lists all previous queries with timestamps and summaries.

**Reusing Query Patterns:**

**User Message:**
```
Show me top customers by revenue like the previous query
```

Agent uses previous queries as examples to generate similar SQL patterns.

#### Planning Mode: Create a Data Product PRP

**User Message:**
```
I want to create a customer analytics dashboard
```

**What happens:**
- Agent discovers relevant source tables
- Presents datasets and asks for confirmation
- Generates targeted questions to gather requirements
- Iterative conversation to fill in requirement gaps
- Creates comprehensive PRP document with 10 standard sections
- Stores PRP in session for Action Mode

**Refining the PRP:**

**User Message:**
```
Add revenue metrics to section 4
```

Agent applies targeted modifications while preserving the overall PRP structure.

#### Action Mode: Execute a PRP to Build Data Product

**User Message:**
```
Create the queries from my PRP
```

**What happens:**
- Agent reads PRP from Planning Mode session
- Discovers source tables matching PRP requirements
- Presents discovered sources with confidence scores
- User approves → Generates SQL queries for each target table
- User approves → Creates complete GraphQL API scaffolding
- Returns file paths to generated API project

**Iterating on a Step:**

**User Message:**
```
Modify the query generation to include more aggregations
```

Agent tracks the modification request and re-runs the appropriate workflow step with the changes applied.

## Configuration

### Agent Settings

- `AGENT_MODEL`: Gemini model to use (default: `gemini-2.0-flash-001`)

### ADK Server Configuration

The ADK API server and web UI support these command-line options:

- `--port INTEGER`: Server port (default: `8000`)
- `--host TEXT`: Binding host (default: `127.0.0.1`)
- `--log_level [debug|info|warning|error|critical]`: Logging level
- `-v, --verbose`: Enable verbose (DEBUG) logging
- `--reload / --no-reload`: Enable auto-reload for development

**Example:**
```bash
poetry run adk api_server --port 8080 --host 0.0.0.0 --verbose
```

### MCP Service URLs

- `DISCOVERY_AGENT_URL`: Data discovery service
- `QUERY_GEN_AGENT_URL`: Query generation service
- `PLANNING_AGENT_URL`: Planning service
- `GRAPHQL_AGENT_URL`: GraphQL generation service
- `APOLLO_MCP_URL`: Apollo MCP server

### Timeouts and Limits

- `HTTP_TIMEOUT`: HTTP request timeout (default: `300.0` seconds)
- `MAX_PLANNING_TURNS`: Max planning conversation turns (default: `10`)
- `MAX_QUERIES_PER_TARGET`: Max queries per target table (default: `3`)
- `MAX_QUERY_ITERATIONS`: Max query refinement iterations (default: `10`)

### BigQuery Configuration

- `BIGQUERY_MAX_RETRIES`: Maximum retry attempts for SQL execution (default: `3`)
- `BIGQUERY_TIMEOUT`: Query execution timeout in seconds (default: `300`)

## Development

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=data_orchestration_agent

# Run specific test file
poetry run pytest tests/unit/test_clients.py
```

### Code Quality

```bash
# Format code
poetry run black src/ tests/

# Lint code
poetry run ruff check src/ tests/
```

## Capabilities Reference

### Ask Mode Capabilities

**Dataset Search and Discovery**
- Search BigQuery catalog using natural language queries
- Filter results by project, dataset, or metadata
- Get ranked results with relevance scoring
- Iterative search refinement with suggested alternatives

**Schema and Metadata Inspection**
- View complete table schemas with column types and descriptions
- See row counts, data freshness, and update timestamps
- Access security classifications (PII, PHI flags)
- Review data quality metrics and profiling information

**SQL Query Generation**
- Convert natural language questions to validated SQL
- Automatically fetch table schemas for accurate query generation
- Support for complex joins, aggregations, and window functions
- Query result limiting and ordering preferences
- Use previous queries as examples/context for new queries

**Query Execution and Management**
- Execute generated SQL queries directly in BigQuery
- View formatted results as markdown tables
- Track query history across sessions
- Rerun or modify previous queries
- View full SQL for any historical query

**Utility Functions**
- Get current timestamp for time-based queries
- Session state inspection
- Query performance insights

### Planning Mode Capabilities

**Conversation Tracking**
- Automatic capture of all user messages and agent responses
- Full context preservation for PRP generation
- Support for long-form requirements documentation
- Handles extended conversations with content storage optimization

**Dataset Discovery and Validation**
- Natural language search for relevant source tables
- Load full dataset metadata into planning session
- Present schemas and data profiles to users
- Confirm dataset coverage before proceeding
- Track all discovered tables for PRP inclusion

**Intelligent Requirement Gathering**
- AI-driven question generation based on conversation gaps
- Context-aware follow-up questions
- Adaptive questioning until requirements are complete
- Support for requirement clarification and refinement

**PRP Document Generation**
- Automated creation of structured PRPs from conversation history
- Includes all 10 standard PRP sections
- Incorporates discovered dataset metadata
- Generates data gap analysis
- Creates realistic example scenarios

**PRP Refinement**
- Targeted modifications to specific sections
- Preserves overall structure while applying changes
- Maintains consistency across modified sections
- Tracks modification history

**Mode Integration**
- Seamless handoff to Action Mode with full context
- Stores PRP content and discovered datasets in session
- Sets flags for downstream workflow detection

### Action Mode Capabilities

**PRP-Based Source Discovery**
- Extracts target table requirements from PRP Section 9
- Searches for matching source tables in BigQuery catalog
- Returns confidence scores for each source match
- Maps source columns to target requirements

**SQL Query Generation from PRPs**
- Generates queries for each target table in the PRP
- Uses discovered source tables and their schemas
- Creates appropriate joins, transformations, and aggregations
- Validates query syntax before returning
- Supports multiple queries per target table

**GraphQL API Scaffolding**
- Generates complete GraphQL schema from SQL queries
- Creates resolver implementations
- Builds deployment-ready project structure
- Includes configuration files and documentation

**Workflow Iteration**
- Modify and rerun any workflow step (discovery, queries, GraphQL)
- Clear downstream artifacts when iterating on earlier steps
- Track modification requests for audit trail
- Support for incremental refinement

**GraphQL Operation Execution**
- Execute queries against deployed GraphQL APIs
- Pass variables to parameterized operations
- Return formatted JSON results

**Session State Management**
- Read planning context from previous modes
- Track workflow progress (discovery → queries → graphql → complete)
- Store artifacts at each step for review
- Manage confirmation flags and pending approvals

## Session State

The agent maintains session state across interactions using prefixed keys for organization:

```python
{
    # Mode tracking
    "current_mode": "ask|planning|action",
    
    # Ask Mode state
    "user:last_search_results": {
        "query": "...",
        "total_count": 10,
        "results": [...]  # Array of discovered datasets
    },
    "user:queries": [
        {
            "query": "SELECT ...",
            "querysummary": "Description",
            "timestamp": "2025-01-01T00:00:00Z",
            "question": "Original question"
        }
    ],
    "user:datasets": {
        "project.dataset.table": {
            "table_id": "project.dataset.table",
            "details": "# Dataset Details\n\nMarkdown content...",
            "timestamp": "2025-01-01T00:00:00Z"
        }
    },
    "user:query_results": [
        {
            "query": "SELECT * FROM ...",
            "timestamp": "2025-01-01T00:00:00Z",
            "result": "# Query Results\n\nMarkdown formatted table..."
        }
    ],
    
    # Planning Mode state (prefixed with user:planning_)
    "user:planning_qahistory": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ],
    "user:planning_discovereddatasets": {
        "project.dataset.table": "markdown metadata...",
    },
    "user:planning_datasetsconfirmed": False,
    "user:planning_intentconfirmed": False,
    "user:planning_prpgenerated": False,
    "user:planning_prpcontent": "",
    
    # Action Mode state (uses legacy keys for backward compatibility)
    "prp_text": "Full PRP markdown document",
    "discovered_datasets": [
        {
            "target_table": "...",
            "sources": [...],
            "mappings": [...]
        }
    ],
    "query_results": [
        {
            "target_table": "...",
            "queries": [...],
            "validation": {...}
        }
    ],
    "graphql_output_path": "/path/to/generated/api",
    "action_step": "discovery|queries|graphql|complete",
    "pending_confirmation": "discovery|queries|None"
}
```

**State Key Conventions:**
- `user:` prefix: Persistent user data across sessions
- `user:planning_` prefix: Planning Mode specific state
- Legacy keys (no prefix): Action Mode state for backward compatibility
- `temp:` prefix: Temporary data (e.g., content storage for long messages)

## Troubleshooting

### Agent Won't Start

#### MCP Services Not Running

The Data Orchestration Agent requires five MCP services to be running:
- Data Discovery Agent (http://localhost:8080)
- Query Generation Agent (http://localhost:8081)
- Data Planning Agent (http://localhost:8082)
- Data GraphQL Agent (http://localhost:8083)
- Apollo MCP Server (http://localhost:8084)

**To deploy all MCP services locally using Docker:**

See [DOCKER_SETUP.md](DOCKER_SETUP.md) for complete instructions. Quick start:

```bash
cd /home/user/git/data-orchestration-agent
docker compose up -d
./check-health.sh
```

This will start all required MCP services and verify they're healthy.

#### Environment Variables

Ensure required variables are set:
- `GCP_PROJECT_ID`: Your Google Cloud project ID
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account key file (see [DOCKER_SETUP.md](DOCKER_SETUP.md) for authentication setup)
- `GOOGLE_API_KEY`: API key for Gemini model access

#### Other Issues

- **Network**: Check firewall rules allow connections to MCP service ports
- **Logs**: Review agent logs at startup for specific error messages
- **Ports**: Ensure ports 8080-8085 are not already in use

### CopilotKit AG-UI Server Issues

#### Server Won't Start

**Port Already in Use:**
```bash
# Check what's using port 8085
lsof -i :8085

# Use a different port
python -m data_orchestration_agent.main --port 8086
```

**Import Errors:**
```bash
# Ensure all dependencies are installed
poetry install

# If ag-ui-adk package is missing
poetry add ag-ui-adk
```

**Dependency Conflicts:**
If you see uvicorn version conflicts:
```bash
# ag-ui-adk requires uvicorn >= 0.35.0
poetry add "uvicorn>=0.35.0"
poetry add ag-ui-adk
```

#### Frontend Connection Issues

If your CopilotKit frontend can't connect:

1. **Verify server is running:**
```bash
curl http://localhost:8085/health
```

2. **Check runtimeUrl in frontend:**
```typescript
// Should point to your server
<CopilotKit runtimeUrl="http://localhost:8085">
```

3. **Check for network issues:**
```bash
# Test from the same machine as frontend
curl -v http://localhost:8085/health
```

4. **Review server logs:**
```bash
python -m data_orchestration_agent.main --verbose
# Look for connection attempts and errors
```

#### WebSocket or Streaming Issues

If real-time communication isn't working:

- **CopilotKit SDK handles protocol**: No manual configuration needed
- **Check browser console**: Look for WebSocket connection errors
- **Verify endpoint**: CopilotKit connects to root path `/`
- **Firewall/Proxy**: Ensure WebSocket connections aren't blocked
- **Test with verbose logging**:
```bash
python -m data_orchestration_agent.main --verbose
# Shows WebSocket connection attempts
```

#### State or Tool Execution Issues

If the agent isn't responding correctly:

1. **Verify ADK agent is working**: Test with ADK development UI first
2. **Check MCP services**: Ensure all 5 MCP services are running and healthy
3. **Review CopilotKit logs**: The SDK provides detailed protocol logging
4. **Test basic chat**: Try simple requests to isolate the issue

For CopilotKit-specific issues, see:
- [CopilotKit Troubleshooting](https://docs.copilotkit.ai/troubleshooting)
- [AG-UI Protocol Issues](https://docs.copilotkit.ai/adk/quickstart?path=exiting-agent)

### BigQuery Query Execution Issues

#### "403 Request had insufficient authentication scopes"

**Cause:** Your access token doesn't have the required OAuth scopes, even if you're the project owner.

**Key Concept:** IAM roles (like Owner) are separate from OAuth scopes. Your IAM role grants *permission*, but the access token needs proper *scopes* to use specific APIs.

**Solution:** Re-authenticate with full cloud-platform scope:

```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/cloud-platform
```

**Why this happens:**
- Default `gcloud auth application-default login` grants limited scopes
- Discovery Engine and BigQuery APIs require explicit scope inclusion
- Even owners need properly scoped tokens
- This is by design for security (principle of least privilege)

**Verify your scopes:**
```bash
gcloud auth application-default print-access-token | \
  python3 -c "import sys, json, base64; token=sys.stdin.read().strip(); payload=token.split('.')[1] + '=' * (4 - len(token.split('.')[1]) % 4); print(json.dumps(json.loads(base64.b64decode(payload)), indent=2))"
```

Look for the `scope` field to confirm it includes `cloud-platform` or specific service scopes.

#### Query Syntax Errors

If generated queries fail with syntax errors:
- Check that table names are fully qualified (`project.dataset.table`)
- Verify source tables exist and are accessible
- Review the full SQL using `view_query(index)` in Ask Mode
- Try regenerating with more specific questions or context

### Planning Mode Issues

#### Session State Not Persisting

If planning context is lost between interactions:
- Check session ID is consistent across requests
- Verify `user:planning_qahistory` exists in session state (use `/session/{session_id}/state` endpoint)
- Ensure conversation tracking tools (`track_user_message`, `track_assistant_message`) are being called
- Review agent logs for state update confirmations

#### PRP Generation Fails

If `generate_prp()` returns errors:
- Ensure Q&A history is not empty (`user:planning_qahistory` must have entries)
- Verify discovered datasets were loaded (`user:planning_discovereddatasets` must exist)
- Check both confirmation flags are set (`user:planning_datasetsconfirmed` and `user:planning_intentconfirmed`)
- Review logs for specific Gemini API errors

### Action Mode Issues

#### Cannot Find PRP

If Action Mode can't locate the PRP:
- Verify `prp_text` key exists in session state
- Check that Planning Mode completed successfully with `user:planning_prpgenerated = True`
- Try using `get_session_state(state_path="planning")` to inspect planning context
- Ensure session ID matches the planning session

#### Workflow Step Failures

If discovery, query generation, or GraphQL creation fails:
- Check `action_step` in session state to see current workflow position
- Review `pending_confirmation` to see if user approval is needed
- Use `iterate_on_step()` to retry with modifications
- Verify MCP service logs (query-gen, graphql) for detailed error messages

#### Query Generation Returns No Results

If `generate_queries_from_discovery()` produces no queries:
- Check that `discovered_datasets` in session state is not empty
- Verify source tables have valid schemas
- Review PRP Section 9 for clear target table specifications
- Try modifying the PRP with more specific requirements

### MCP Service Connection Issues

If tools fail with connection errors:
- **Test connectivity**: `curl http://localhost:PORT/health` for each service
- **Check logs**: Review MCP service logs for startup errors
- **Verify URLs**: Ensure environment variables have correct service URLs
- **Firewall**: Confirm no firewall blocking localhost connections
- **Restart services**: Try restarting individual MCP services

### Query History Not Appearing

If `view_query()` shows no queries:
- Verify queries were generated (not just searched for datasets)
- Check `user:queries` key in session state
- Ensure session ID is consistent across requests
- Try generating a new query with `generate_query()` to test

## License

See LICENSE file for details.

## Contributing

Contributions welcome! Please follow the existing code style and add tests for new features.

