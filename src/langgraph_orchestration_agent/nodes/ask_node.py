"""Ask mode node for data discovery and exploration."""

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ..config import Config
from ..llm import create_llm
from ..state import AgentState
from ..tools.ask_tools import create_ask_tools
from ..tools.state_manager import AskModeStateManager

logger = logging.getLogger(__name__)


async def ask_node(
    state: AgentState, config: Config, clients: dict[str, Any]
) -> dict[str, Any]:
    """Process messages in Ask mode for data discovery and exploration.

    This node implements a full tool-calling agent loop:
    1. Initialize state manager with current state
    2. Create tools with bound dependencies
    3. Bind tools to LLM
    4. Execute agent loop: invoke LLM → check for tool calls → execute tools → repeat
    5. Return updated state with messages and tool state

    Args:
        state: Current agent state
        config: Agent configuration
        clients: Dictionary of MCP clients (discovery, query_gen, graphql)

    Returns:
        Updated state dictionary with new messages and updated tool state
    """
    logger.info("Entering ask_node")

    # Initialize mode if needed
    if "current_mode" not in state:
        state["current_mode"] = "ask"

    # Get messages
    messages = state.get("messages", [])
    if not messages:
        logger.warning("No messages in state")
        return {"messages": messages, "current_mode": "ask"}

    last_message = messages[-1]
    if not isinstance(last_message, HumanMessage):
        logger.warning("Last message is not a HumanMessage")
        return state

    # Initialize state manager with current state
    state_manager = AskModeStateManager(state)

    # Create tools with bound dependencies
    discovery_client = clients.get("discovery")
    query_gen_client = clients.get("query_gen")

    if not discovery_client or not query_gen_client:
        logger.error("Missing required MCP clients")
        error_msg = AIMessage(
            content="Error: Missing required MCP clients for ask mode"
        )
        return {"messages": messages + [error_msg], "current_mode": "ask"}

    tools = create_ask_tools(discovery_client, query_gen_client, state_manager)

    # Handle selected datasets from frontend context
    selected_datasets = state.get("selected_datasets", [])
    dataset_context = ""
    missing_datasets: list[str] = []
    
    if selected_datasets:
        logger.info(f"Processing {len(selected_datasets)} selected datasets from context")
        dataset_details: list[str] = []
        
        for table_id in selected_datasets:
            cached_dataset = state_manager.get_dataset(table_id)
            if cached_dataset:
                dataset_details.append(
                    f"**Dataset: {table_id}**\n{cached_dataset.get('details', 'No details available')}"
                )
            else:
                missing_datasets.append(table_id)
        
        if dataset_details:
            dataset_context = (
                "\n\n**User has selected the following datasets for context:**\n\n"
                + "\n\n".join(dataset_details)
                + "\n\n"
            )
    
    # Fetch missing datasets if any
    if missing_datasets:
        logger.info(f"Fetching details for {len(missing_datasets)} uncached datasets")
        for table_id in missing_datasets:
            try:
                # Parse table ID
                parts = table_id.split(".")
                if len(parts) != 3:
                    logger.warning(f"Invalid table ID format: {table_id}")
                    continue
                
                project_id, dataset_id, table_name = parts
                
                # Fetch details from discovery client
                result = await discovery_client.get_asset_details(
                    project_id, dataset_id, table_name
                )
                
                if result and result != "Asset not found":
                    # Cache the dataset
                    state_manager.add_dataset(table_id, result)
                    dataset_context += f"\n\n**Dataset: {table_id}**\n{result}\n"
                else:
                    logger.warning(f"Dataset not found: {table_id}")
                    dataset_context += f"\n\n**Dataset: {table_id}**\nDataset not found\n"
            except Exception as e:
                logger.error(f"Failed to fetch dataset {table_id}: {e}")
                dataset_context += f"\n\n**Dataset: {table_id}**\nError fetching details: {e}\n"

    # Create LLM and bind tools
    llm = create_llm(config)
    llm_with_tools = llm.bind_tools(tools)

    # Create system message for ask mode
    system_msg_content = """You are a Data Explorer helping users discover and query BigQuery data."""
    
    # Prepend dataset context if available
    if dataset_context:
        system_msg_content = dataset_context + "\n\n" + system_msg_content
    
    system_msg_content += """

**CRITICAL - Handling Non-Data Questions**:
- If the user is just greeting you, making small talk, or asking general questions, respond naturally WITHOUT calling any tools
- Examples of non-data interactions: "hi", "hello", "wazzup", "how are you", "what's up", "thanks", "bye"
- Only use tools when the user is ACTUALLY asking about datasets, schemas, or wants to query/explore data
- If you're unsure whether to use tools: if it's not clearly a data request, just respond conversationally
- You can explain your capabilities, but don't search for datasets unless explicitly asked

**Your Tools** (only use for actual data tasks):
- search_datasets(query) - Find tables with natural language
- get_dataset_details(table_id) - View table schema and metadata
  * You MUST call this tool whenever the user asks about a table whose name matches the fully qualified pattern "project.dataset.table" or explicitly requests schema/column/field details.
- generate_query(question, tables, max_rows_returned=10, previous_query_indices="") - Create SQL query from question
  * Tables must be fully qualified: "project_id.dataset_id.table_id"
  * previous_query_indices: Optional comma-separated string of query indices to use as examples (e.g., "0,2")
  * Use previous queries when user references them or wants similar patterns
  * Extract table IDs from search_datasets results
- run_query(query_index) - Execute a query (0 = most recent)
- view_query(query_index) - View query SQL or list all queries (-1 to list all)
- get_current_time() - Get current timestamp

**Typical Workflow**:
1. User asks about data → search_datasets("user's question")
2. User wants schema → get_dataset_details("project.dataset.table")
3. User asks data question → search_datasets(question), identify relevant table(s), generate_query(question, "project.dataset.table") then run_query(0)
4. User wants history → view_query(-1) to list all, or view_query(2) for specific

**CRITICAL - Search Strategy (Iterative Refinement)**:
1. **Initial Search**: When user asks about data, pass their question to search_datasets
   - Preserve important terms: domain entities (NFL, products), actions (backtest, forecast, analyze), and qualifiers
   - Remove only filler words (what, do, I, have, to, the)
   - When in doubt, include the term rather than exclude it

2. **Evaluate Results**: After getting search results, assess relevance
   - Do the returned tables match the user's intent?
   - Are key concepts from their question represented?
   - Example: If they asked about "backtest" but results show only "predictions", results may be incomplete

3. **Refine When Needed**: If results seem poor or incomplete, SUGGEST CONCRETE ALTERNATIVES:
   - Explain what you found vs. what they asked for
   - Offer specific alternative search terms based on domain knowledge
   - Examples:
     * "I found tables about 'predictions' but not specifically 'live inference'. Would you like me to search for: 'real-time predictions', 'online inference', 'streaming predictions', or 'prediction API'?"
     * "The results show historical data. Were you looking for: 'real-time data', 'live scores', 'current game data', or 'in-progress games'?"
     * "I see 'backtest' results but they focus on training. Should I search for: 'test set evaluation', 'model validation', 'holdout predictions', or 'out-of-sample testing'?"
   - Always provide 3-4 specific alternative terms/phrases the user can choose from
   - If you're unsure, ask what aspect they care about (timing, format, use case) and suggest options

4. **Iterate**: Use user feedback to do a refined search with better terms
   - ALWAYS do a fresh search when user refines their request
   - Do NOT rely on previous search results when criteria change

**Query Management**:
- All queries saved automatically in session
- "What queries have I run?" → view_query(-1)
- "Rerun the query about X" → find index with view_query(-1), then run_query(index)
- **Using Previous Queries as Context**: Pass previous_query_indices to generate_query when:
  * User says "like the previous query" or "similar to query X"
  * User wants to modify/extend an earlier query pattern
  * Building on established query patterns or join logic
  * Example: generate_query("Show top 10 products by revenue", "project.dataset.sales", previous_query_indices="0,2")

**Guidelines**:
- Be conversational and clear
- Show data as-is, don't over-interpret
- Suggest refinements if results don't match intent
- Always prepend your responses with: # Ask Mode
- Be thorough in explaining what data is available
- Help users understand table schemas, row counts, and data freshness
- Suggest relevant tables based on user's questions

Be helpful and efficient."""
    
    system_msg = SystemMessage(content=system_msg_content)

    # Build message history for LLM (system + conversation messages)
    conversation_messages = [system_msg] + messages

    # Agent execution loop
    max_iterations = 10
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        logger.info(f"Ask mode iteration {iteration}/{max_iterations}")

        try:
            # Invoke LLM with tools
            response = llm_with_tools.invoke(conversation_messages)

            # Check if response contains tool calls
            tool_calls = getattr(response, "tool_calls", None)

            if not tool_calls:
                # No tool calls - final response
                logger.info("No tool calls in response, returning final answer")
                ai_message = AIMessage(content=response.content)
                updated_messages = messages + [ai_message]

                return {
                    "messages": updated_messages,
                    "current_mode": "ask",
                    # Update state with tool state
                    "queries": state.get("queries", []),
                    "query_results": state.get("query_results", []),
                    "datasets": state.get("datasets", {}),
                    "last_search_results": state.get("last_search_results"),
                }

            # Execute tool calls
            logger.info(f"Executing {len(tool_calls)} tool call(s)")

            # Add AI message with tool calls to conversation
            conversation_messages.append(response)

            # Execute each tool call
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_call_id = tool_call["id"]

                logger.info(f"Calling tool: {tool_name} with args: {tool_args}")

                # Find the tool function
                tool_func = None
                for tool in tools:
                    if tool.name == tool_name:
                        tool_func = tool
                        break

                if not tool_func:
                    logger.error(f"Tool not found: {tool_name}")
                    tool_result = f"Error: Tool {tool_name} not found"
                else:
                    try:
                        # Execute tool (async)
                        tool_result = await tool_func.ainvoke(tool_args)
                        logger.info(
                            f"Tool {tool_name} executed successfully: {len(str(tool_result))} chars"
                        )
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name}: {e}")
                        tool_result = f"Error executing {tool_name}: {e}"

                # Add tool result to conversation
                tool_message = ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
                conversation_messages.append(tool_message)

            # Continue loop to get LLM's response after tool execution

        except Exception as e:
            logger.error(f"Error in ask mode agent loop: {e}")
            error_msg = AIMessage(content=f"# Ask Mode\n\nError: {e}")
            return {
                "messages": messages + [error_msg],
                "current_mode": "ask",
            }

    # Max iterations reached
    logger.warning(f"Max iterations ({max_iterations}) reached in ask mode")
    timeout_msg = AIMessage(
        content="# Ask Mode\n\nI've reached the maximum number of steps. Please try simplifying your request."
    )
    return {
        "messages": messages + [timeout_msg],
        "current_mode": "ask",
    }
