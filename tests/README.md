# Data Orchestration Agent Testing Guide

This directory contains comprehensive tests for the Data Orchestration Agent, including CLI-based scenario tests and pytest-based integration tests.

## Overview

The testing framework supports two main types of tests:

1. **CLI Scenario Tests** - Interactive or scripted tests that simulate real user workflows
2. **Integration Tests** - Pytest-based tests with mocked dependencies

## Directory Structure

```
tests/
├── README.md                           # This file
├── cli_test_runner.py                  # CLI test runner
├── conftest.py                         # Pytest fixtures
├── scenarios/                          # Test scenario JSON files
│   ├── nfl_backtest_scenario.json      # NFL predictions backtest workflow
│   └── simple_discovery_scenario.json  # Basic discovery workflow
├── integration/                        # Integration tests
│   └── test_orchestration_scenarios.py # Orchestration scenario tests
└── unit/                               # Unit tests
    └── test_tools.py                   # Tool-level tests
```

## Running Tests

### CLI Scenario Tests

#### Interactive Mode

Start an interactive testing session where you can chat with the agent:

```bash
# Using the script
./scripts/run_cli_test.sh --interactive

# Or directly
poetry run python tests/cli_test_runner.py --interactive
```

**Interactive Commands:**
- Type your message to chat with the agent
- `summary` - Show conversation summary
- `export <filename>` - Export conversation history to JSON
- `clear` - Clear conversation history
- `exit` or `quit` - End the session

#### Scenario Mode

Run a predefined test scenario:

```bash
# Run NFL backtest scenario
./scripts/run_cli_test.sh nfl_backtest

# Run simple discovery scenario
./scripts/run_cli_test.sh simple_discovery

# Run custom scenario file
./scripts/run_cli_test.sh path/to/scenario.json

# Or directly with Python
poetry run python tests/cli_test_runner.py --scenario tests/scenarios/nfl_backtest_scenario.json
```

**Scenario Files:**
- `nfl_backtest_scenario.json` - Full workflow from discovery to mode switching
- `simple_discovery_scenario.json` - Basic data discovery and table details

### Integration Tests

Run pytest-based integration tests:

```bash
# Using the script
./scripts/run_integration_tests.sh

# Or directly
poetry run pytest tests/integration/test_orchestration_scenarios.py -v

# With coverage
poetry run pytest tests/integration/ --cov=data_orchestration_agent --cov-report=html
```

## Creating Test Scenarios

Test scenarios are defined in JSON format with the following structure:

```json
{
  "name": "Scenario Name",
  "description": "Detailed description",
  "session_id": "unique-session-id",
  "export_history": "optional/output/path.json",
  "steps": [
    {
      "step": 1,
      "description": "Step description",
      "message": "User message to send",
      "assertions": [
        {
          "type": "contains",
          "value": "expected text in response"
        },
        {
          "type": "tool_called",
          "value": "expected_tool_name"
        }
      ],
      "wait": 1.0
    }
  ]
}
```

### Assertion Types

- **`contains`** - Response must contain the specified text (case-insensitive)
- **`tool_called`** - The specified tool must be called in the step
- **`not_contains`** - Response must NOT contain the specified text
- **`equals`** - Response must exactly match the value

### Example Scenario

```json
{
  "name": "Customer Data Discovery",
  "description": "Search for customer tables and get details",
  "session_id": "customer-test",
  "steps": [
    {
      "step": 1,
      "description": "Search for customer data",
      "message": "show me customer data tables",
      "assertions": [
        {
          "type": "tool_called",
          "value": "search_datasets"
        },
        {
          "type": "contains",
          "value": "customer"
        }
      ]
    },
    {
      "step": 2,
      "description": "Get table details",
      "message": "tell me more about the first table",
      "assertions": [
        {
          "type": "tool_called",
          "value": "get_dataset_details"
        },
        {
          "type": "contains",
          "value": "schema"
        }
      ]
    }
  ]
}
```

## Environment Setup

Before running tests, ensure your environment is configured:

1. **Install dependencies:**
   ```bash
   poetry install
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Required environment variables:**
   - `GOOGLE_API_KEY` - Google GenAI API key
   - `GCP_PROJECT_ID` - GCP project ID
   - Other service URLs (see `.env.example`)

**Note:** The test scripts (`./scripts/run_cli_test.sh` and `./scripts/run_integration_tests.sh`) automatically load environment variables from the `.env` file before running tests.

## Test Output

### CLI Test Output

CLI tests produce detailed output including:
- User messages
- Agent responses
- Tool calls with arguments and results
- Assertion pass/fail status
- Summary statistics

Example output:
```
================================================================================
USER: what data do I have to backtest my nfl predictions?
================================================================================

🔧 TOOL CALL: search_datasets
   Arguments: {
     "query": "backtest nfl predictions"
   }
   Result: {
     "status": "simulated",
     "data": {...}
   }

AGENT: I found several datasets for backtesting NFL predictions...

✅ Assertion passed: Tool 'search_datasets' was called
✅ Assertion passed: Response contains 'backtest'
```

### Test History Export

Export conversation history to JSON for analysis:

```bash
# In interactive mode
export test_output/my_session.json

# Or configure in scenario JSON
"export_history": "test_output/scenario_results.json"
```

### Integration Test Output

Integration tests produce pytest output with coverage:
```
tests/integration/test_orchestration_scenarios.py::TestOrchestrationScenarios::test_nfl_backtest_scenario_mock PASSED
tests/integration/test_orchestration_scenarios.py::TestOrchestrationScenarios::test_mode_switching_workflow PASSED

---------- coverage: platform linux, python 3.10.12 -----------
Name                                              Stmts   Miss  Cover
---------------------------------------------------------------------
src/data_orchestration_agent/agents/ask_agent.py     45      2    96%
...
```

## Troubleshooting

### Common Issues

**Issue: `GOOGLE_API_KEY not set`**
```bash
# Solution: Set the API key in .env
echo "GOOGLE_API_KEY=your-api-key-here" >> .env
```

**Issue: `Poetry not found`**
```bash
# Solution: Install poetry
curl -sSL https://install.python-poetry.org | python3 -
```

**Issue: `Connection refused` to agent services**
```bash
# Solution: Ensure services are running
docker-compose up -d
# Or start services individually
```

**Issue: Tests fail with import errors**
```bash
# Solution: Reinstall dependencies
poetry install --no-cache
```

## Best Practices

1. **Start with interactive mode** to explore agent behavior
2. **Create scenarios** for repeatable tests
3. **Use assertions** to validate behavior
4. **Export history** for debugging
5. **Run integration tests** before committing code
6. **Add new scenarios** for bug reports and edge cases

## CI/CD Integration

To run tests in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Integration Tests
  run: |
    poetry install
    poetry run pytest tests/integration/ -v --cov=data_orchestration_agent
    
- name: Run CLI Tests
  run: |
    poetry run python tests/cli_test_runner.py --scenario tests/scenarios/nfl_backtest_scenario.json --quiet
```

## Contributing

When adding new tests:

1. Create scenario files in `tests/scenarios/`
2. Add integration tests in `tests/integration/`
3. Update this README with new scenarios
4. Ensure all tests pass before submitting PRs

## Additional Resources

- [Google ADK Documentation](https://github.com/google/adk)
- [Pytest Documentation](https://docs.pytest.org/)
- [Project README](../README.md)

