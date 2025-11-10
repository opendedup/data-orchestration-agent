"""LangChain tools for ask mode - search, query generation, and execution."""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import google.auth
from google.cloud import bigquery
from langchain_core.tools import tool

from .state_manager import AskModeStateManager

logger = logging.getLogger(__name__)


def create_ask_tools(
    discovery_client: Any,
    query_gen_client: Any,
    state_manager: AskModeStateManager,
) -> list:
    """Create LangChain tools for ask mode with bound dependencies.

    Args:
        discovery_client: Data discovery MCP client
        query_gen_client: Query generation MCP client
        state_manager: State manager for session data

    Returns:
        List of LangChain tools
    """

    @tool
    async def search_datasets(
        query: str, project_id: str = "", max_results: int = 5
    ) -> str:
        """Search for BigQuery datasets using natural language query.

        Use this tool to find tables and datasets in BigQuery based on the user's question.
        The search results are stored in session state for use by other tools.

        Args:
            query: Natural language search query describing what data you're looking for
            project_id: Optional GCP project ID to filter results (leave empty for all projects)
            max_results: Maximum number of results to display (default: 5)

        Returns:
            Human-readable summary of search results with table names and descriptions
        """
        try:
            logger.info(f"Searching datasets: {query}")

            # Build filters
            filters = {"output_format": "json"}
            if project_id:
                filters["project_id"] = project_id

            # Get JSON-formatted results from discovery agent
            result = await discovery_client.query_data_assets(query, filters)

            if not result or result == "No results found":
                search_results = {
                    "results": [],
                    "total_count": 0,
                    "query": query,
                    "message": "No datasets found matching your query.",
                }
            else:
                try:
                    search_results = json.loads(result)
                    search_results["query"] = query
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse discovery response: {e}")
                    return f"Error: Invalid response format from discovery service: {e}"

            # Store in session state
            state_manager.set_last_search_results(search_results)

            # Return human-readable summary
            total = search_results.get("total_count", 0)
            results = search_results.get("results", [])

            if total == 0:
                return "No datasets found matching your query."

            summary = f"Found {total} dataset(s):\n\n"
            for i, r in enumerate(results[:max_results], 1):
                table_id = f"{r['project_id']}.{r['dataset_id']}.{r['table_id']}"
                desc = r.get("description", "No description")
                row_count = r.get("row_count", "Unknown")
                summary += f"{i}. **{table_id}**\n"
                summary += f"   - Description: {desc}\n"
                summary += f"   - Rows: {row_count}\n\n"

            if total > max_results:
                summary += f"... and {total - max_results} more\n\n"

            return summary

        except Exception as e:
            logger.error(f"Error searching datasets: {e}")
            return f"Error searching datasets: {e}"

    @tool
    async def get_dataset_details(table_id: str) -> str:
        """Get detailed metadata for a specific BigQuery table including schema and statistics.

        Use this tool when you need to see the full schema, column names, types, and descriptions
        for a specific table.

        Args:
            table_id: Full table ID in format project.dataset.table

        Returns:
            Markdown-formatted table details with schema, columns, and statistics
        """
        try:
            logger.info(f"Getting details for table: {table_id}")

            # Parse table ID
            parts = table_id.split(".")
            if len(parts) != 3:
                return "Invalid table ID format. Expected: project.dataset.table"

            project_id, dataset_id, table_name = parts

            # Get markdown-formatted details from discovery agent
            result = await discovery_client.get_asset_details(
                project_id, dataset_id, table_name
            )

            if not result or result == "Asset not found":
                return f"Table not found: {table_id}"

            # Store in state
            state_manager.add_dataset(table_id, result)

            return result

        except Exception as e:
            logger.error(f"Error getting dataset details: {e}")
            return f"Error getting dataset details: {e}"

    @tool
    async def generate_query(
        question: str,
        tables: str,
        max_rows_returned: int = 10,
        previous_query_indices: str = "",
        should_execute: bool = False,
    ) -> str:
        """Generate SQL query from a natural language question using specified tables.

        This tool creates a SQL query that answers the user's question. The query generation
        agent will automatically fetch full dataset metadata for the specified tables.

        Args:
            question: Natural language question to answer with SQL
            tables: Comma-separated list of fully qualified table names (e.g., "project.dataset.table1, project.dataset.table2")
            max_rows_returned: Maximum number of rows to return in query results (default: 10)
            previous_query_indices: Optional comma-separated list of up to 3 query indices to use as examples (e.g., "0,2")
            should_execute: Set to True if the user explicitly wants to execute the query immediately and see results. 
                          Set to False (default) if the user just wants to see the query or is asking "what would the query be".
                          Examples where should_execute=True: "show me the data", "run the query", "get me the results", "fetch the data"
                          Examples where should_execute=False: "what is X?", "create a query for Y", "generate SQL for Z"

        Returns:
            Human-readable summary with SQL preview and query index for execution
        """
        try:
            logger.info(f"Generating SQL for: {question}")

            # Parse tables
            table_list = [t.strip() for t in tables.split(",") if t.strip()]
            if not table_list:
                return "Error: No tables provided. Please specify at least one fully qualified table name."

            # Parse fully qualified table names into dataset IDs
            dataset_ids = []
            for fq_table_name in table_list:
                parts = fq_table_name.split(".")
                if len(parts) != 3:
                    logger.warning(f"Invalid table name: {fq_table_name}")
                    continue

                project_id, dataset_id, table_name = parts
                dataset_ids.append({
                    "project_id": project_id,
                    "dataset_id": dataset_id,
                    "table_id": table_name,
                })

            if not dataset_ids:
                return "Error: None of the specified tables have valid fully qualified names (format: project.dataset.table)."

            # Process previous_query_indices
            examples_section = ""
            if previous_query_indices:
                try:
                    indices = [
                        int(idx.strip())
                        for idx in previous_query_indices.split(",")
                        if idx.strip()
                    ]
                    queries = state_manager.list_queries()

                    # Validate indices
                    invalid = [idx for idx in indices if idx < 0 or idx >= len(queries)]
                    if invalid:
                        return f"Error: Invalid query indices: {invalid}. Valid range: 0-{len(queries)-1}"

                    # Limit to 3
                    selected_indices = indices[:3]

                    # Format as examples
                    examples_section = "Previous Query Examples:\n\n"
                    for idx in selected_indices:
                        query_entry = queries[idx]
                        examples_section += f"-- Question: {query_entry['question']}\n"
                        examples_section += f"-- Summary: {query_entry['querysummary']}\n"
                        examples_section += f"```sql\n{query_entry['query']}\n```\n\n"

                    logger.info(f"Including {len(selected_indices)} previous queries as examples")
                except ValueError as e:
                    return f"Error parsing previous_query_indices: {e}"

            # Augment insight with query preferences
            augmented_insight = (
                f"{question}\n\n"
                f"Query Requirements:\n"
                f"- Limit results to {max_rows_returned} rows maximum\n"
                f"- Prioritize most recent records (ORDER BY timestamp/date DESC) unless otherwise specified\n"
                f"- Return aggregates whenever possible unless otherwise specified"
            )

            # Prepend examples if present
            if examples_section:
                augmented_insight = examples_section + "\n" + augmented_insight

            # Call query generation client
            response = await query_gen_client.generate_queries(
                insight=augmented_insight, dataset_ids=dataset_ids
            )

            # Parse response
            try:
                query_data = json.loads(response) if isinstance(response, str) else response
            except json.JSONDecodeError:
                return "Error: Invalid response from query generation service"

            # Extract queries
            generated_queries = query_data.get("queries", [])
            if not generated_queries:
                failure_diagnostic = query_data.get(
                    "failure_diagnostic", "No queries generated"
                )
                return f"Error: No valid queries generated. {failure_diagnostic}"

            # Get the best query
            best_query = generated_queries[0]
            sql_query = best_query.get("sql", "")
            description = best_query.get("description", question)

            if not sql_query:
                return "Error: No SQL query generated"

            # Store query in state
            query_index = state_manager.add_query(sql_query, description, question)

            # Return summary
            sql_preview = sql_query[:200] + "..." if len(sql_query) > 200 else sql_query

            result = f"**Query #{query_index} Generated**\n\n"
            result += f"**Summary**: {description}\n\n"
            result += f"**SQL Preview**:\n```sql\n{sql_preview}\n```\n\n"
            result += f"Run this query with: run_query({query_index})"

            return result

        except Exception as e:
            logger.error(f"Error generating query: {e}")
            return f"Error generating query: {e}"

    @tool
    async def run_query(query_index: int = 0) -> str:
        """Execute a SQL query from session history and return formatted results.

        Use this tool to execute a query that was previously generated with generate_query.
        Results are formatted as a markdown table.

        Args:
            query_index: Index of query to execute (0 = most recent, default: 0)

        Returns:
            Formatted query results as markdown table with row count and SQL
        """
        try:
            logger.info(f"Executing query #{query_index}")

            # Get query from state
            query_entry = state_manager.get_query(query_index)
            if not query_entry:
                queries = state_manager.list_queries()
                if not queries:
                    return "Error: No queries found. Please generate a query first with generate_query."
                return f"Error: Query index {query_index} out of range. Available queries: 0 to {len(queries)-1}"

            sql_query = query_entry["query"]
            description = query_entry["querysummary"]

            # Execute SQL
            credentials, project = google.auth.default()
            project_id = os.getenv("GCP_PROJECT_ID") or project

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

            # Add data rows (limit to 100 for display)
            max_display_rows = 100
            rows_to_show = rows[:max_display_rows]

            for row in rows_to_show:
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

            # Add SQL in collapsible section
            result += f"\n<details>\n<summary>SQL Query</summary>\n\n```sql\n{sql_query}\n```\n</details>\n"

            # Store result
            state_manager.add_result(sql_query, result)

            logger.info(f"Query executed successfully, returned {row_count} rows")
            return result

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return f"Error executing query: {e}"

    @tool
    async def view_query(query_index: int = -1) -> str:
        """View SQL query history or a specific query.

        Use this tool to see what queries have been generated in this session, or to view
        the full SQL of a specific query.

        Args:
            query_index: Index of specific query to view, or -1 to list all queries (default: -1)

        Returns:
            Formatted query details or list of all queries
        """
        try:
            queries = state_manager.list_queries()

            if not queries:
                return "No queries have been generated yet. Use generate_query to create a SQL query."

            # If -1, list all queries
            if query_index == -1:
                result = f"# Query History ({len(queries)} queries)\n\n"
                for i, q in enumerate(queries):
                    summary = q.get("querysummary", "No summary")
                    timestamp = q.get("timestamp", "Unknown time")
                    result += f"{i}. **{summary}**\n"
                    result += f"   - Time: {timestamp}\n"
                    result += f"   - Question: {q.get('question', 'N/A')}\n\n"

                result += "\nUse view_query(index) to see full SQL for a specific query."
                return result

            # Show specific query
            query_entry = state_manager.get_query(query_index)
            if not query_entry:
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
            result += f"Run this query with: run_query({query_index})"

            return result

        except Exception as e:
            logger.error(f"Error viewing query: {e}")
            return f"Error viewing query: {e}"

    @tool
    async def get_current_time() -> str:
        """Get the current date and time.

        Use this tool when you need to know what time it is, for example to filter data
        by recent dates or to understand temporal context.

        Returns:
            Current timestamp in ISO 8601 format with timezone
        """
        now = datetime.now(timezone.utc)
        return f"Current time: {now.isoformat()}"

    return [
        search_datasets,
        get_dataset_details,
        generate_query,
        run_query,
        view_query,
        get_current_time,
    ]

