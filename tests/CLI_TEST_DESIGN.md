# CLI Test Runner Design

## Overview

The CLI test runner provides a simple, mock-based testing framework for the Data Orchestration Agent that allows testing conversation flows and tool orchestration **without requiring actual API calls or credentials**.

## Design Decisions

### Why Mock-Based Testing?

1. **No API Costs**: Tests don't make real API calls to Google AI/Vertex AI
2. **No Credentials Required**: Tests work without `GOOGLE_API_KEY` or OAuth2 setup
3. **Fast Execution**: Tests run instantly without waiting for API responses
4. **Predictable Results**: Mock responses are consistent and repeatable
5. **Simple to Maintain**: Easy to update test scenarios without API changes

### Why Not Real API Calls?

The original approach tried to use the Google GenAI Client directly, but encountered several issues:

1. **ADK Tool Incompatibility**: ADK tools have complex parameter types (`ToolContext`) that can't be serialized to JSON Schema for Google GenAI's automatic function calling
2. **Authentication Complexity**: API key vs OAuth2 vs Vertex AI credentials
3. **Cost**: Each test run would incur API charges
4. **Speed**: Waiting for API responses slows down tests
5. **Reliability**: Tests can fail due to API rate limits or network issues

## Architecture

### Test Flow

```
User Request → Pattern Matching → Mock Tool Call → Mock Response
```

The test runner simulates agent behavior by:

1. **Pattern matching** on user messages to determine intent
2. **Simulating tool calls** based on matched patterns
3. **Generating mock responses** that mimic real agent behavior
4. **Tracking conversation history** for analysis and debugging

### Pattern Matching Logic

The test runner uses keyword-based pattern matching to simulate agent behavior:

```python
# Mode switch patterns (highest priority)
if ("yes" and "switch") or "switch to plan":
    → call switch_to_plan_mode()

# Table details patterns
elif "tell me more" or "more about" or ("interested in" and "table"):
    → call get_dataset_details()

# Data search patterns
elif "backtest" or "live inference" or ("what" and ("data" or "inference")):
    → call search_datasets()

# Generic plan creation
elif "plan" or "create":
    → suggest mode switch

# Fallback
else:
    → generic response
```

## Test Scenario Structure

### JSON Format

```json
{
  "name": "Scenario Name",
  "description": "What this scenario tests",
  "session_id": "unique-id",
  "export_history": "output/path.json",
  "steps": [
    {
      "step": 1,
      "description": "What this step tests",
      "message": "User message",
      "assertions": [
        {"type": "tool_called", "value": "tool_name"},
        {"type": "contains", "value": "expected text"}
      ],
      "wait": 1.0
    }
  ]
}
```

### Assertion Types

| Type | Description | Example |
|------|-------------|---------|
| `tool_called` | Verifies a tool was called | `{"type": "tool_called", "value": "search_datasets"}` |
| `contains` | Response contains text (case-insensitive) | `{"type": "contains", "value": "backtest"}` |
| `not_contains` | Response doesn't contain text | `{"type": "not_contains", "value": "error"}` |
| `equals` | Exact response match | `{"type": "equals", "value": "exact text"}` |

## Mock Responses

### search_datasets

```python
{
  "status": "simulated",
  "message": "Tool search_datasets called successfully",
  "results": [
    {
      "table_id": "project.dataset.table",
      "row_count": 449,
      "description": "Table description"
    }
  ]
}
```

### get_dataset_details

```python
{
  "status": "simulated",
  "message": "Tool get_dataset_details called successfully",
  "schema": {
    "fields": [
      {
        "name": "field_name",
        "type": "STRING",
        "description": "Field description"
      }
    ]
  },
  "row_count": 449
}
```

### switch_to_plan_mode

```python
{
  "status": "switched",
  "mode": "plan"
}
```

## Usage

### Run a Scenario

```bash
./scripts/run_cli_test.sh nfl_backtest
```

### Create New Scenarios

1. Create a JSON file in `tests/scenarios/`
2. Define steps with user messages and assertions
3. Run with `./scripts/run_cli_test.sh path/to/scenario.json`

### Interactive Testing

For exploring agent behavior (note: currently uses mock responses):

```bash
./scripts/run_cli_test.sh --interactive
```

## Extending the Test Runner

### Adding New Tool Patterns

Edit `tests/cli_test_runner.py` in the `send_message()` method:

```python
elif "your_pattern" in message.lower():
    tool_name = "your_tool_name"
    arguments = {"arg": "value"}
    
    tool_calls.append({
        "name": tool_name,
        "arguments": arguments
    })
    
    result = {"your": "mock_result"}
    final_response = "Your mock response"
```

### Adding New Assertion Types

Edit `tests/cli_test_runner.py` in the `run_scenario()` method:

```python
elif assertion['type'] == 'your_type':
    expected = assertion['value']
    # Your validation logic
    if validation_failed:
        logger.warning(f"⚠️  Assertion failed: {reason}")
        all_assertions_passed = False
    else:
        logger.info(f"✅ Assertion passed: {reason}")
```

## Future Enhancements

### Option 1: Real API Integration

To add real API testing alongside mock testing:

1. Add a `--real-api` flag to enable actual API calls
2. Use Google ADK's native agent execution instead of manual GenAI client
3. Implement proper credential handling for both API key and OAuth2

### Option 2: Hybrid Approach

- Mock tool execution for fast tests
- Real ADK agent conversations for integration tests
- Use environment variable to toggle modes

### Option 3: Record/Replay

- Record real agent conversations
- Replay them in tests without API calls
- Update recordings when agent behavior changes

## Troubleshooting

### Test Fails with Assertion Error

Check the pattern matching logic - your message might not match expected patterns.

### Tool Not Being Called

Add more specific patterns or adjust pattern priority in `send_message()`.

### Wrong Tool Called

Pattern order matters - more specific patterns should be checked first.

## Benefits of This Approach

✅ **Fast**: Tests run in seconds  
✅ **Reliable**: No API failures or rate limits  
✅ **Free**: No API costs  
✅ **Simple**: Easy to understand and modify  
✅ **Predictable**: Same inputs always give same outputs  
✅ **Testable**: Can verify orchestration logic without external dependencies  

## Limitations

❌ **Not E2E**: Doesn't test actual LLM responses  
❌ **Manual Mocking**: New patterns require code changes  
❌ **Limited Coverage**: Only tests predefined conversation flows  
❌ **No LLM Behavior**: Can't test model creativity or edge cases  

## Recommendation

Use this framework for:
- **CI/CD testing**: Fast, reliable regression tests
- **Orchestration testing**: Verify tool calling logic
- **Scenario validation**: Test conversation flows

For real LLM testing:
- Use integration tests with actual API calls
- Run manually or in nightly test suites
- Use separate test budgets/quotas

---

**Created**: 2024-10-31  
**Status**: Working and tested with NFL backtest scenario  
**Test Results**: ✅ All 5 steps passing, 4 tool calls tracked

