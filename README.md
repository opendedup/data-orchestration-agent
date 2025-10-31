# Data Orchestration Agent

Root orchestration agent for data discovery, planning, and product creation using Google's Agent Development Kit (ADK).

## Overview

The Data Orchestration Agent provides a unified interface for working with multiple specialized data agents through three operational modes:

- **Ask Mode**: Explore datasets and query GraphQL APIs
- **Planning Mode**: Gather requirements and create Data Product Requirement Prompts (PRPs)
- **Action Mode**: Execute PRPs to build complete data products

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
- Natural language search for BigQuery datasets
- Detailed table metadata retrieval
- **BigQuery data analysis with SQL query execution**
- GraphQL operation discovery and execution
- Ad-hoc data exploration

### Planning Mode
- Interactive requirement gathering
- Guided conversation for data product design
- Automated PRP generation
- Structured planning workflow

### Action Mode
- PRP-driven source discovery
- Automated SQL query generation
- GraphQL API scaffolding
- Multi-step workflow with user confirmations
- Iterative refinement capabilities

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
```bash
poetry run data-orchestration-agent
```

The agent will start on `http://localhost:8085` by default.

## Usage

### REST API

#### Health Check
```bash
curl http://localhost:8085/health
```

#### Start a Chat Session
```bash
curl -X POST http://localhost:8085/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my-session-123",
    "message": "Help me find customer data"
  }'
```

#### Get Session State
```bash
curl http://localhost:8085/session/my-session-123/state
```

#### Delete Session
```bash
curl -X DELETE http://localhost:8085/session/my-session-123
```

### Example Workflows

#### Ask Mode: Explore Datasets
```json
{
  "session_id": "session-1",
  "message": "Show me all tables related to customer orders"
}
```

The agent will use `search_datasets` tool to find relevant tables.

#### Ask Mode: Analyze Data with BigQuery
```json
{
  "session_id": "session-1",
  "message": "How many bets were placed last week?"
}
```

**First Query Flow:**
1. Agent uses `search_datasets` to discover relevant tables (e.g., "bets", "wagers")
2. Agent analyzes results and selects best 1-3 candidate tables
3. Agent calls `analyze_with_bigquery` with question and candidate tables
4. BigQuery sub-agent examines schemas, generates SQL, executes queries
5. Results are returned to user with context

**Follow-up Query:**
```json
{
  "session_id": "session-1",
  "message": "How do those bets compare to backtesting for the same week?"
}
```

The agent leverages conversation context:
- Checks if previously discovered tables can answer the question
- Reuses tables when appropriate (avoids redundant discovery)
- Performs new discovery only if new data sources are needed
- Maintains smart context awareness across related questions

#### Planning Mode: Create a PRP
```json
{
  "session_id": "session-2",
  "message": "I want to create a customer analytics dashboard"
}
```

The agent will:
1. Start a planning session
2. Ask clarifying questions
3. Generate a structured PRP document

#### Action Mode: Execute a PRP
```json
{
  "session_id": "session-3",
  "message": "Execute the PRP I just created"
}
```

The agent will:
1. Discover source tables from PRP
2. Generate SQL queries (with confirmation)
3. Create GraphQL API (with confirmation)

## Configuration

### Agent Settings

- `AGENT_MODEL`: Gemini model to use (default: `gemini-2.0-flash-001`)
- `AGENT_HOST`: Host address (default: `0.0.0.0`)
- `AGENT_PORT`: Port number (default: `8085`)

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

## Tools Reference

### Ask Mode Tools

#### `search_datasets(query: str, project_id: Optional[str])`
Search for BigQuery datasets using natural language.

#### `get_dataset_details(table_id: str)`
Get detailed metadata for a specific table (format: `project.dataset.table`).

#### `analyze_with_bigquery(question: str, candidate_tables: list[str])`
Analyze BigQuery tables to answer a user question. The BigQuery sub-agent will:
- Examine table schemas using `get_table_info`
- Generate appropriate SQL queries
- Execute queries in BigQuery
- Return formatted results

**Error Handling:**
- Permission errors (403): Immediate failure with clear message
- Query errors: Up to 3 retry attempts with automatic SQL correction
- Detailed failure descriptions after max retries

**Example:**
```python
analyze_with_bigquery(
    question="How many orders were placed last week?",
    candidate_tables=["project.dataset.orders", "project.dataset.customers"]
)
```

#### `list_graphql_operations()`
List available GraphQL operations from Apollo MCP.

#### `query_graphql_data(operation_name: str, variables: Optional[dict])`
Execute a GraphQL query.

### Planning Mode Tools

#### `start_planning(initial_intent: str)`
Start a planning session with initial description.

#### `answer_planning_questions(user_response: str)`
Continue planning conversation with user answers.

#### `generate_prp()`
Generate the final PRP document.

### Action Mode Tools

#### `discover_sources_from_prp()`
Discover source tables from PRP Section 9.

#### `generate_queries_from_discovery(approve_discovery: bool)`
Generate SQL queries from discovered sources.

#### `create_graphql_api(approve_queries: bool, project_name: str)`
Generate GraphQL API from validated queries.

#### `iterate_on_step(step_name: str, modifications: str)`
Request modifications to a previous step (`discovery`, `queries`, or `graphql`).

## Session State

The agent maintains session state across interactions:

```python
{
    "current_mode": "ask|planning|action",
    "planning_session_id": "...",
    "planning_complete": False,
    "prp_text": "...",
    "discovered_datasets": [...],
    "query_results": [...],
    "graphql_output_path": "...",
    "action_step": "discovery|queries|graphql|complete",
    "pending_confirmation": "..."
}
```

## Troubleshooting

### Agent won't start
- Check that all MCP services are running on their configured ports
- Verify `GCP_PROJECT_ID` and `GOOGLE_APPLICATION_CREDENTIALS` are set
- Ensure `GOOGLE_API_KEY` is valid for Gemini API access

### BigQuery Analysis Issues

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

### Tool execution fails
- Check MCP service logs for errors
- Verify network connectivity to MCP services
- Ensure proper authentication credentials

### Planning session not progressing
- Check `planning_session_id` is stored in session state
- Verify planning agent is responding correctly
- Try starting a new session

### Action mode stuck
- Check which `action_step` is current in session state
- Verify PRP text exists in session
- Review pending confirmations

## License

See LICENSE file for details.

## Contributing

Contributions welcome! Please follow the existing code style and add tests for new features.

