"""Query generation and execution tools for BigQuery."""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)

# Global client instances
_query_gen_client = None
_bigquery_agent = None


def set_clients(query_gen_client: Any, bigquery_agent: Any) -> None:
    """Set the global client instances.
    
    Args:
        query_gen_client: Query generation client instance
        bigquery_agent: BigQuery agent instance
    """
    global _query_gen_client, _bigquery_agent
    _query_gen_client = query_gen_client
    _bigquery_agent = bigquery_agent


def _get_queries_from_state(tool_context: ToolContext) -> List[Dict[str, Any]]:
    """Get queries list from context state, initializing if needed.
    
    Args:
        tool_context: ADK tool context with session access
        
    Returns:
        List of query dictionaries
    """
    # Use tool_context.state directly - it automatically handles persistence via event system
    queries = tool_context.state.get("user:queries")
    if queries is None:
        logger.info("Initializing user:queries in context state")
        tool_context.state["user:queries"] = []
        return []
    
    logger.info(f"Found {len(queries)} queries in context state")
    return queries


def _get_query_results_from_state(tool_context: ToolContext) -> List[Dict[str, Any]]:
    """Get query results list from context state, initializing if needed.
    
    Args:
        tool_context: ADK tool context with session access
        
    Returns:
        List of query result dictionaries
    """
    query_results = tool_context.state.get("user:query_results")
    if query_results is None:
        logger.info("Initializing user:query_results in context state")
        tool_context.state["user:query_results"] = []
        return []
    
    logger.info(f"Found {len(query_results)} query results in context state")
    return query_results


async def generate_query(
    tool_context: ToolContext, 
    question: str, 
    tables: List[str],
    max_rows_returned: int = 10,
    previous_query_indices: Optional[List[int]] = None
) -> str:
    """Generate SQL query from a natural language question.
    
    Generates a SQL query that answers the user's question using the specified tables.
    The query generation agent will automatically fetch full dataset metadata.
    
    Args:
        tool_context: ADK tool context with session state access
        question: Natural language question to answer with SQL
        tables: List of fully qualified table names (<project_id>.<dataset_id>.<table_id>)
        max_rows_returned: Maximum number of rows to return in query results (default: 10)
        previous_query_indices: Optional list of up to 3 query indices to use as examples 
            for context (e.g., [0, 2])
        
    Returns:
        Human-readable summary with SQL preview and query index
    """
    logger.warning(f"🔵 TOOL CALLED: generate_query | question={question[:100]}... | tables={tables} | max_rows={max_rows_returned} | prev_indices={previous_query_indices}")
    try:
        if not _query_gen_client:
            return "Error: Query generation client not initialized"
        
        if not tables:
            return "Error: No tables provided. Please specify at least one fully qualified table name."
        
        # Parse fully qualified table names into dataset IDs
        dataset_ids = []
        for fq_table_name in tables:
            # Parse fully qualified name: <project_id>.<dataset_id>.<table_id>
            parts = fq_table_name.split('.')
            if len(parts) != 3:
                logger.warning(f"Invalid fully qualified table name: {fq_table_name}")
                continue
            
            project_id, dataset_id, table_id = parts
            dataset_ids.append({
                "project_id": project_id,
                "dataset_id": dataset_id,
                "table_id": table_id
            })
        
        if not dataset_ids:
            return "Error: None of the specified tables have valid fully qualified names (format: project_id.dataset_id.table_id)."
        
        # Get current queries from context state for validation
        queries = _get_queries_from_state(tool_context)
        
        # Validate and process previous_query_indices
        examples_section = ""
        if previous_query_indices:
            # Check for invalid indices
            invalid_indices = [idx for idx in previous_query_indices if idx < 0 or idx >= len(queries)]
            if invalid_indices:
                return f"Error: Invalid query indices: {invalid_indices}. Valid range: 0-{len(queries)-1}"
            
            # Limit to 3 queries
            selected_indices = previous_query_indices[:3]
            if len(previous_query_indices) > 3:
                logger.info(f"Limiting previous queries from {len(previous_query_indices)} to 3")
            
            # Format previous queries as examples
            examples_section = "Previous Query Examples:\n\n"
            for idx in selected_indices:
                query_entry = queries[idx]
                examples_section += f"-- Question: {query_entry['question']}\n"
                examples_section += f"-- Summary: {query_entry['querysummary']}\n"
                examples_section += f"```sql\n{query_entry['query']}\n```\n\n"
            
            logger.info(f"Including {len(selected_indices)} previous queries as examples: {selected_indices}")
        
        logger.info(f"Generating SQL for question: {question[:100]}...")
        logger.info(f"Using {len(dataset_ids)} table(s): {', '.join(tables)}")
        
        # Augment insight with query preferences
        augmented_insight = (
            f"{question}\n\n"
            f"Query Requirements:\n"
            f"- Limit results to {max_rows_returned} rows maximum\n"
            f"- Prioritize most recent records (ORDER BY timestamp/date DESC) unless otherwise specified\n"
            f"- Return aggregates whenever possible unless otherwise specified"
        )
        
        # Prepend examples section if present
        if examples_section:
            augmented_insight = examples_section + "\n" + augmented_insight
        
        # Call query generation client
        response = await _query_gen_client.generate_queries(
            insight=augmented_insight,
            dataset_ids=dataset_ids
        )
        
        # Parse response
        try:
            query_data = json.loads(response) if isinstance(response, str) else response
        except json.JSONDecodeError:
            return f"Error: Invalid response from query generation service"
        
        # Extract queries from response
        generated_queries = query_data.get("queries", [])
        if not generated_queries:
            # Check if there's a failure diagnostic
            failure_diagnostic = query_data.get("failure_diagnostic", "No queries generated")
            return f"Error: No valid queries generated. {failure_diagnostic}"
        
        # Get the best query (generate_queries returns only the best one)
        best_query = generated_queries[0]
        sql_query = best_query.get("sql", "")
        description = best_query.get("description", question)
        
        if not sql_query:
            return "Error: No SQL query generated"
        
        # Create new query entry
        query_entry = {
            "query": sql_query,
            "querysummary": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "question": question
        }
        
        # Append to queries list
        queries.append(query_entry)
        
        # Store back to context.state - this automatically persists via event delta
        tool_context.state["user:queries"] = queries
        
        # Diagnostic logging
        logger.info(f"generate_query: Stored query via tool_context.state")
        logger.info(f"generate_query: session_id = {tool_context.session.id}")
        logger.info(f"generate_query: Total queries stored = {len(queries)}")
        
        query_index = len(queries) - 1
        
        # Return summary with SQL preview
        sql_preview = sql_query[:200] + "..." if len(sql_query) > 200 else sql_query
        
        result = f"**Query #{query_index} Generated**\n\n"
        result += f"**Summary**: {description}\n\n"
        result += f"**SQL Preview**:\n```sql\n{sql_preview}\n```\n\n"
        result += f"Run this query with: `run_query({query_index})`"
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating query: {e}", exc_info=True)
        return f"Error generating query: {str(e)}"


async def run_query(tool_context: ToolContext, query_index: int = 0) -> str:
    """Execute a SQL query from session history.
    
    Args:
        tool_context: ADK tool context with session state access
        query_index: Index of query to execute (0 = most recent, -1 = oldest)
        
    Returns:
        Formatted query results as markdown table
    """
    logger.warning(f"🟢 TOOL CALLED: run_query | query_index={query_index}")
    try:
        if not _bigquery_agent:
            return "Error: BigQuery agent not initialized"
        
        # Get queries from context state
        queries = _get_queries_from_state(tool_context)
        
        # Get current query results from context state
        query_results = _get_query_results_from_state(tool_context)
        
        # Diagnostic logging
        logger.info(f"run_query: session_id = {tool_context.session.id}")
        logger.info(f"run_query: Retrieved {len(queries)} queries from context state")
        
        if not queries:
            return "Error: No queries found. Please generate a query first with generate_query()."
        
        # Get query by index
        try:
            query_entry = queries[query_index]
        except IndexError:
            return f"Error: Query index {query_index} out of range. Available queries: 0 to {len(queries)-1}"
        
        sql_query = query_entry["query"]
        description = query_entry["querysummary"]
        
        logger.info(f"Executing query #{query_index}: {description}")
        
        # Execute SQL
        from google.cloud import bigquery
        import google.auth
        
        # Get credentials and create client
        credentials, project = google.auth.default()
        project_id = os.getenv('GCP_PROJECT_ID') or project
        
        if not project_id:
            return "Error: GCP_PROJECT_ID not configured"
        
        # Create BigQuery client
        client = bigquery.Client(project=project_id, credentials=credentials)
        
        # Execute query in thread pool
        logger.info(f"Executing SQL (length: {len(sql_query)} chars)")
        query_job = await asyncio.to_thread(client.query, sql_query)
        
        # Wait for results
        results = await asyncio.to_thread(query_job.result)
        rows = await asyncio.to_thread(list, results)
        
        if not rows:
            return f"Query executed successfully but returned 0 rows.\n\n**Summary**: {description}\n\n**SQL**:\n```sql\n{sql_query}\n```"
        
        # Format results as markdown table
        field_names = [field.name for field in results.schema]
        row_count = len(rows)
        
        # Build markdown table
        result = f"# Query Results (Query #{query_index})\n\n"
        result += f"**Summary**: {description}\n\n"
        result += f"**Total Rows**: {row_count:,}\n\n"
        
        # Create table header
        header_row = "| " + " | ".join(field_names) + " |"
        separator_row = "|" + "|".join(["---" for _ in field_names]) + "|"
        
        result += header_row + "\n"
        result += separator_row + "\n"
        
        # Add data rows (limit to 100 rows for display)
        max_display_rows = 100
        rows_to_show = rows[:max_display_rows]
        
        for row in rows_to_show:
            # Convert row to dict and escape values
            values = []
            for field in field_names:
                value = row.get(field)
                if value is None:
                    values.append("NULL")
                else:
                    # Escape special characters
                    str_value = str(value).replace("|", "\\|").replace("\n", " ")
                    values.append(str_value)
            
            data_row = "| " + " | ".join(values) + " |"
            result += data_row + "\n"
        
        # Add footer
        if row_count > max_display_rows:
            result += f"\n*... {row_count - max_display_rows} more rows not shown*\n"
        
        # Add SQL query in collapsible section
        result += f"\n<details>\n<summary>SQL Query</summary>\n\n```sql\n{sql_query}\n```\n</details>\n"
        
        # Store query result in session state
        result_entry = {
            "query": sql_query,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": result
        }
        
        query_results.append(result_entry)
        tool_context.state["user:query_results"] = query_results
        
        logger.info(f"Query executed successfully, returned {row_count} rows")
        return result
        
    except Exception as e:
        logger.error(f"Error executing query: {e}", exc_info=True)
        return f"Error executing query: {str(e)}"


async def view_query(
    tool_context: ToolContext,
    query_index: Optional[int] = None
) -> str:
    """View SQL query history or a specific query.
    
    Args:
        tool_context: ADK tool context with session state access
        query_index: Optional index of specific query to view (if None, lists all)
        
    Returns:
        Formatted query details or list of all queries
    """
    logger.warning(f"🟡 TOOL CALLED: view_query | query_index={query_index}")
    try:
        # Get queries from context state
        queries = _get_queries_from_state(tool_context)
        
        if not queries:
            return "No queries have been generated yet. Use generate_query() to create a SQL query."
        
        # If no index specified, list all queries
        if query_index is None:
            result = f"# Query History ({len(queries)} queries)\n\n"
            for i, q in enumerate(queries):
                summary = q.get("querysummary", "No summary")
                timestamp = q.get("timestamp", "Unknown time")
                result += f"{i}. **{summary}**\n"
                result += f"   - Time: {timestamp}\n"
                result += f"   - Question: {q.get('question', 'N/A')}\n\n"
            
            result += "\nUse `view_query(index)` to see full SQL for a specific query."
            return result
        
        # Show specific query
        try:
            query_entry = queries[query_index]
        except IndexError:
            return f"Error: Query index {query_index} out of range. Available queries: 0 to {len(queries)-1}"
        
        sql_query = query_entry["query"]
        summary = query_entry["querysummary"]
        timestamp = query_entry["timestamp"]
        question = query_entry.get("question", "N/A")
        
        result = f"# Query #{query_index}\n\n"
        result += f"**Summary**: {summary}\n\n"
        result += f"**Question**: {question}\n\n"
        result += f"**Timestamp**: {timestamp}\n\n"
        result += f"**SQL**:\n```sql\n{sql_query}\n```\n\n"
        result += f"Run this query with: `run_query({query_index})`"
        
        return result
        
    except Exception as e:
        logger.error(f"Error viewing query: {e}", exc_info=True)
        return f"Error viewing query: {str(e)}"

