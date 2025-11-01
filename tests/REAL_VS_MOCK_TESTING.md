# Real API vs Mock Testing - Complete Guide

## TL;DR

✅ **For Real API Testing:** Start the HTTP server and use `test_http_client.py` or `cli_test_runner_simple.py --real-api`  
✅ **For Fast Mock Testing:** Use the original `cli_test_runner.py` (default)

## Why Two Approaches?

### The Challenge

Google ADK agents have complex internal APIs that aren't designed for direct external use:
- `agent.run_async()` returns streaming generators
- Requires `InvocationContext` objects
- Tool serialization issues with `ToolContext` types
- Not straightforward to call agents directly in tests

### The Solution

**Don't fight ADK's internal APIs!** Instead:

1. **Mock Testing** - Simulate agent behavior for fast iteration
2. **HTTP Testing** - Test through the server which already has proper ADK integration

## Approach 1: Mock Testing (Fast & Recommended for Development)

### Files
- `tests/cli_test_runner.py` - Full-featured mock runner (original)
- `tests/cli_test_runner_simple.py` - Simplified version

### Usage

```bash
# Original (detailed mocks)
./scripts/run_cli_test.sh nfl_backtest

# Simple version
poetry run python tests/cli_test_runner_simple.py --scenario tests/scenarios/nfl_backtest_scenario.json
```

### Pros
- ⚡ **Instant execution** (no API latency)
- 💰 **Zero cost** (no API charges)
- 🔒 **No credentials needed** (for basic testing)
- 🔄 **Perfect for CI/CD** (fast, reliable, repeatable)
- 🐛 **Easy debugging** (predictable behavior)

### Cons
- ❌ Doesn't test actual LLM reasoning
- ❌ Mock logic needs manual updates
- ❌ Can drift from real behavior

### Best For
- Local development
- CI/CD pipelines  
- Regression testing
- Orchestration logic verification
- Quick iteration

## Approach 2: HTTP Testing (Real API Calls)

### Files
- `tests/test_http_client.py` - Dedicated HTTP client
- `tests/cli_test_runner_simple.py --real-api` - CLI runner with HTTP mode
- `src/data_orchestration_agent/main.py` - The HTTP server

### Usage

**Step 1: Start Services**
```bash
# Start MCP services
docker-compose up -d

# Start orchestration agent server
poetry run python -m data_orchestration_agent.main
# Server runs on http://localhost:8085
```

**Step 2: Run Tests**
```bash
# Option A: Dedicated HTTP client
poetry run python tests/test_http_client.py

# Option B: CLI runner with --real-api flag
poetry run python tests/cli_test_runner_simple.py \
  --scenario tests/scenarios/nfl_backtest_scenario.json \
  --real-api
```

### Pros
- ✅ **True E2E testing** (real LLM, real tools)
- ✅ **Tests actual behavior** (not mocked)
- ✅ **Catches integration issues**
- ✅ **Validates full stack**

### Cons
- 🐌 Slow (API latency + processing)
- 💸 Costs money (API charges)
- 🔌 Requires running services
- 🔐 Needs credentials (`GOOGLE_API_KEY`)
- ❌ Not suitable for CI/CD

### Best For
- Pre-release validation
- Feature demonstration
- Integration testing
- Manual verification
- Bug reproduction

## Detailed Comparison

| Aspect | Mock Testing | HTTP Testing |
|--------|-------------|--------------|
| **Execution Time** | < 5 seconds | 30-60+ seconds |
| **API Costs** | $0 | ~$0.01-0.10 per run |
| **Setup Required** | None | Server + all services |
| **Credentials** | Optional | Required |
| **LLM Testing** | No (simulated) | Yes (real Gemini) |
| **Tool Execution** | Simulated | Real (via MCP) |
| **Network Required** | No | Yes |
| **CI/CD Friendly** | Excellent | Poor |
| **Debugging** | Easy | Complex |
| **Maintenance** | Update mocks | Auto-syncs |

## Recommended Testing Strategy

### Daily Development
```bash
# Quick iteration with mocks
./scripts/run_cli_test.sh nfl_backtest
```

### Pre-Commit
```bash
# Fast validation
./scripts/run_cli_test.sh nfl_backtest
./scripts/run_integration_tests.sh
```

### Feature Testing
```bash
# Start server in terminal 1
poetry run python -m data_orchestration_agent.main

# Test in terminal 2
poetry run python tests/test_http_client.py
```

### CI/CD Pipeline
```yaml
# GitHub Actions example
- name: Run Mock Tests
  run: ./scripts/run_cli_test.sh nfl_backtest

- name: Run Integration Tests  
  run: poetry run pytest tests/integration/
```

### Weekly/Release
```bash
# Manual full integration test
docker-compose up -d
poetry run python -m data_orchestration_agent.main &
sleep 10
poetry run python tests/test_http_client.py
```

## Implementation Details

### Why Not Direct ADK Agent Calls?

We initially tried:
```python
# This looked simple but doesn't work:
response = await agent.run_async(message)
```

**Problems encountered:**
1. Returns async generator (streaming), not response
2. Needs `InvocationContext`, not just strings
3. ADK tools can't serialize to JSON Schema
4. Complex internal state management

**The realization:**
> The HTTP server (`main.py`) already solves all these problems!  
> It has proper ADK integration. Just test through HTTP.

### Mock Implementation

```python
class MockAgentTester:
    async def send_message(self, message: str) -> str:
        # Pattern matching on message
        if "backtest" in message.lower():
            return "Found backtest datasets..."
        # Return simulated response
```

### HTTP Implementation

```python
class HTTPAgentTester:
    async def send_message(self, message: str) -> str:
        # Call actual server
        response = await self.client.post(
            f"{self.base_url}/chat",
            json={"session_id": self.session_id, "message": message}
        )
        return response.json()["response"]
```

## Environment Configuration

### Mock Testing
```bash
# Minimal - just for agent initialization
GCP_PROJECT_ID=your-project
```

### HTTP Testing
```bash
# Full configuration required
GOOGLE_API_KEY=your-api-key-here
GCP_PROJECT_ID=your-project-id
DISCOVERY_AGENT_URL=http://localhost:8080
QUERY_GEN_AGENT_URL=http://localhost:8081
GRAPHQL_AGENT_URL=http://localhost:8083
APOLLO_MCP_URL=http://localhost:8084
```

## Creating New Test Scenarios

### Scenario JSON Format
```json
{
  "name": "My Test Scenario",
  "description": "What this tests",
  "steps": [
    {
      "step": 1,
      "description": "First step",
      "message": "User message here",
      "assertions": [
        {"type": "contains", "value": "expected text"}
      ],
      "wait": 1.0
    }
  ]
}
```

**Works with both mock and HTTP testing!**

## Troubleshooting

### Mock Tests Issues

**Pattern not matching:**
- Update `cli_test_runner.py` pattern matching logic
- Add more specific patterns

**Assertions failing:**
- Check mock responses match expectations
- Update scenario assertions

### HTTP Tests Issues

**"Could not connect":**
```bash
# Make sure server is running
ps aux | grep "data_orchestration_agent.main"
poetry run python -m data_orchestration_agent.main
```

**"API key not set":**
```bash
# Add to .env
echo "GOOGLE_API_KEY=your-key" >> .env
```

**"Service connection refused":**
```bash
# Check all services
docker-compose ps
./check-health.sh
```

**Slow responses:**
- Normal for real API calls
- Increase timeout if needed

## Future Enhancements

### Hybrid Mode
```bash
# Switch between modes with flag
./scripts/run_cli_test.sh nfl_backtest --mode=mock   # Fast
./scripts/run_cli_test.sh nfl_backtest --mode=http   # Real
```

### Record/Replay
```bash
# Record real conversations
./scripts/run_cli_test.sh --record nfl_backtest

# Replay as mocks
./scripts/run_cli_test.sh --replay nfl_backtest
```

### Parallel Testing
```bash
# Run both in parallel, compare results
./scripts/run_cli_test.sh --compare nfl_backtest
```

## Summary

| Use Case | Recommendation |
|----------|---------------|
| Daily dev | Mock testing |
| CI/CD | Mock testing |
| Feature demo | HTTP testing |
| Bug fix | Mock first, HTTP to verify |
| Release | HTTP testing |
| Learning | Start with mock, graduate to HTTP |

**Bottom line:** Mock testing for speed and iteration. HTTP testing for validation and confidence. Use both strategically!

---

**Questions?** See `REAL_API_TESTING.md` for more details or `tests/README.md` for general testing documentation.

