# Testing Quick Start Guide

Quick reference for running tests on the Data Orchestration Agent.

## Prerequisites

```bash
# Install dependencies
poetry install

# Set up environment
cp .env.example .env
# Edit .env with your credentials (especially GOOGLE_API_KEY)
```

**Note:** The test scripts automatically load environment variables from `.env` file, so you don't need to manually export them.

## Quick Commands

### Interactive Testing (Recommended for exploring)

```bash
# Start interactive session
./scripts/run_cli_test.sh --interactive

# Or with poetry
poetry run python tests/cli_test_runner.py --interactive
```

**Interactive Commands:**
- Chat with agent naturally
- `summary` - View conversation summary
- `export <file>` - Save history to JSON
- `clear` - Reset conversation
- `exit` - Quit session

### Scenario Testing (Recommended for CI/CD)

```bash
# Run NFL backtest scenario
./scripts/run_cli_test.sh nfl_backtest

# Run simple discovery scenario
./scripts/run_cli_test.sh simple_discovery

# Run custom scenario
./scripts/run_cli_test.sh path/to/scenario.json
```

### Integration Tests (Unit/Mock Testing)

```bash
# Run all integration tests
./scripts/run_integration_tests.sh

# Or with pytest directly
poetry run pytest tests/integration/ -v
```

## Example Workflow

### 1. Explore the Agent Interactively

```bash
./scripts/run_cli_test.sh --interactive
```

```
You: what data do I have about customers?
Agent: [searches and shows results]

You: tell me more about the first table
Agent: [shows detailed schema]

You: summary
[Shows conversation stats]

You: exit
```

### 2. Create a Test Scenario

Create `tests/scenarios/my_test.json`:

```json
{
  "name": "My Test",
  "description": "Test my workflow",
  "steps": [
    {
      "step": 1,
      "description": "Search for data",
      "message": "show me customer tables",
      "assertions": [
        {"type": "tool_called", "value": "search_datasets"}
      ]
    }
  ]
}
```

### 3. Run Your Scenario

```bash
./scripts/run_cli_test.sh tests/scenarios/my_test.json
```

### 4. Run Integration Tests

```bash
./scripts/run_integration_tests.sh
```

## Available Test Scenarios

| Scenario | Description | Command |
|----------|-------------|---------|
| **nfl_backtest** | Full NFL predictions workflow | `./scripts/run_cli_test.sh nfl_backtest` |
| **simple_discovery** | Basic data discovery | `./scripts/run_cli_test.sh simple_discovery` |

## Test Output

### CLI Tests
- Real-time conversation display
- Tool call logging
- Assertion validation
- Summary statistics
- Optional history export

### Integration Tests
- Pytest output
- Code coverage report
- HTML coverage: `htmlcov/index.html`

## Common Issues

**Missing API Key:**
```bash
export GOOGLE_API_KEY="your-key-here"
# Or add to .env file
```

**Service Connection Errors:**
```bash
# Make sure services are running
docker-compose up -d
./check-health.sh
```

**Import Errors:**
```bash
poetry install --no-cache
```

## Learn More

- Full documentation: [tests/README.md](tests/README.md)
- Scenario structure: [tests/README.md#creating-test-scenarios](tests/README.md#creating-test-scenarios)
- CI/CD integration: [tests/README.md#cicd-integration](tests/README.md#cicd-integration)

## Quick Tips

✅ **Start with interactive mode** to understand agent behavior  
✅ **Create scenarios** for repeatable tests  
✅ **Use assertions** to validate expected behavior  
✅ **Export history** for debugging  
✅ **Run integration tests** before committing  

## Examples from the Screenshots

Based on the conversation shown in your screenshots, here's how to test it:

**Interactive:**
```bash
./scripts/run_cli_test.sh --interactive

You: what data do I have to backtest my nfl predictions?
You: what about live inferences
You: ok it looks like I am interested in backtest_regression_inferences and regression_predictions tell me more about these tables
You: great lets create a plan
You: yes switch to plan mode
You: summary
```

**As a Scenario:**
```bash
./scripts/run_cli_test.sh nfl_backtest
```

This runs the pre-built scenario that matches your conversation flow!

## Next Steps

1. Try interactive mode: `./scripts/run_cli_test.sh --interactive`
2. Run existing scenarios: `./scripts/run_cli_test.sh nfl_backtest`
3. Create your own scenarios based on your workflows
4. Add integration tests for new features
5. Run tests in CI/CD

Happy testing! 🚀

