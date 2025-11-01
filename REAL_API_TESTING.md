# Real API Testing Guide

## Overview

There are two ways to test the Data Orchestration Agent:

1. **Mock-Based CLI Tests** (Default) - Fast, no API costs, perfect for CI/CD
2. **Real API HTTP Tests** - Full end-to-end testing with actual LLM calls

## Option 1: Mock-Based Testing (Recommended for CI/CD)

The CLI test runner (`tests/cli_test_runner.py`) uses mock responses by default:

```bash
./scripts/run_cli_test.sh nfl_backtest
```

**Pros:**
- ✅ Fast execution (seconds)
- ✅ No API costs
- ✅ No credentials needed for basic testing
- ✅ Predictable, repeatable results
- ✅ Perfect for regression testing

**Cons:**
- ❌ Doesn't test actual LLM behavior
- ❌ Mock responses need manual updates

**Use for:**
- CI/CD pipelines
- Local development
- Regression testing
- Orchestration logic verification

## Option 2: Real API Testing via HTTP Server

For true end-to-end testing with real API calls:

### Step 1: Start the Orchestration Agent Server

```bash
# Make sure services are running
docker-compose up -d

# Start the orchestration agent
poetry run python -m data_orchestration_agent.main
```

The server will start on `http://localhost:8085`

### Step 2: Run HTTP-Based Tests

```bash
# Run the HTTP test script
poetry run python tests/test_http_client.py
```

Or use `curl` for manual testing:

```bash
# Health check
curl http://localhost:8085/health

# Send a message
curl -X POST http://localhost:8085/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-123",
    "message": "what data do I have to backtest my nfl predictions?"
  }'
```

### Step 3: Interactive Testing

```bash
# Use the interactive CLI against the live server
# (Requires modifying cli_test_runner.py to use HTTP client)
```

## Why Not Direct ADK Agent Execution?

We initially tried calling ADK agents directly in the test runner:

```python
# This doesn't work easily:
response = await agent.run_async(message)
```

**Issues encountered:**
1. ADK's `run_async()` returns an async generator (streaming)
2. Requires proper `InvocationContext` objects, not just strings
3. Complex internal APIs not designed for direct external use
4. Tool serialization issues with ADK's `ToolContext` types

**Solution:**
The HTTP server (`main.py`) already has all the proper ADK integration. Testing through HTTP gives us real API calls without fighting ADK's internal APIs.

## Environment Requirements

### For Mock Testing:
- None! Works out of the box

### For Real API Testing:
- `GOOGLE_API_KEY` - For Gemini model access
- `GCP_PROJECT_ID` - Your GCP project
- All MCP services running (discovery, query-gen, etc.)

## Comparison

| Feature | Mock Tests | HTTP Tests |
|---------|-----------|------------|
| **Speed** | Fast (seconds) | Slow (API latency) |
| **Cost** | Free | API charges apply |
| **Setup** | None | Server + services |
| **LLM Testing** | No | Yes |
| **Tool Testing** | Logic only | Full integration |
| **CI/CD** | Excellent | Not recommended |
| **Debugging** | Easy | More complex |

## Recommendations

### Development Workflow:

1. **Daily dev work** → Use mock tests
2. **Feature testing** → Use HTTP tests with local server
3. **Pre-commit** → Run mock tests
4. **CI/CD** → Run mock tests only
5. **Weekly/release** → Run HTTP tests manually

### Test Strategy:

```bash
# Fast feedback loop (use frequently)
./scripts/run_cli_test.sh nfl_backtest

# Full integration (use occasionally)
poetry run python -m data_orchestration_agent.main &
sleep 5
poetry run python tests/test_http_client.py
```

## Creating HTTP Test Scenarios

```python
from tests.test_http_client import OrchestrationAgentHTTPTester

async def my_test():
    tester = OrchestrationAgentHTTPTester()
    
    # Send messages
    response1 = await tester.send_message("your question here")
    response2 = await tester.send_message("follow-up question")
    
    # Check responses
    assert "expected text" in response1
    
    # Print summary
    tester.print_summary()
    
    await tester.close()
```

## Troubleshooting

### Mock Tests Fail
- Check pattern matching logic in `cli_test_runner.py`
- Update mock responses if needed
- Ensure `.env` is configured (for agent initialization)

### HTTP Tests Fail

**"Could not connect to server":**
```bash
# Start the server first
poetry run python -m data_orchestration_agent.main
```

**"API key not set":**
```bash
# Add to .env
GOOGLE_API_KEY=your-key-here
```

**"Service connection refused":**
```bash
# Start MCP services
docker-compose up -d
./check-health.sh
```

## Future Enhancements

### Hybrid Approach
- Add `--mock/--real` flag to CLI test runner
- Switch between mock and HTTP clients
- Same scenarios work for both modes

### Record/Replay
- Record real API conversations
- Replay them as mocks for fast testing
- Update recordings when agent changes

### Integration Test Suite
- Separate test suite for HTTP tests
- Run in nightly builds
- Generate coverage reports

---

**Summary:** Use mock tests for development and CI/CD. Use HTTP tests for occasional full integration verification. Both have their place in a comprehensive testing strategy!

