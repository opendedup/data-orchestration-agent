"""Action Mode tools for executing PRPs and building data products."""

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Global client instances (will be injected by main.py)
_discovery_client = None
_query_gen_client = None
_graphql_client = None
_apollo_mcp_client = None
_bigquery_agent = None
_session_state = {}


def set_clients(
    discovery_client: Any,
    query_gen_client: Any,
    graphql_client: Any,
    apollo_mcp_client: Optional[Any] = None
) -> None:
    """Set the global client instances.
    
    Args:
        discovery_client: Data discovery client instance
        query_gen_client: Query generation client instance
        graphql_client: GraphQL client instance
        apollo_mcp_client: Apollo MCP client instance (optional)
    """
    global _discovery_client, _query_gen_client, _graphql_client, _apollo_mcp_client
    _discovery_client = discovery_client
    _query_gen_client = query_gen_client
    _graphql_client = graphql_client
    _apollo_mcp_client = apollo_mcp_client


def set_bigquery_agent(bigquery_agent: Any) -> None:
    """Set the BigQuery agent instance.
    
    Args:
        bigquery_agent: BigQuery agent instance
    """
    global _bigquery_agent
    _bigquery_agent = bigquery_agent


def set_session_state(state: Dict[str, Any]) -> None:
    """Set the session state reference.
    
    Args:
        state: Session state dictionary
    """
    global _session_state
    _session_state = state


def _extract_target_schemas(prp_text: str) -> List[Dict[str, Any]]:
    """Extract target table schemas from PRP Section 9.
    
    Args:
        prp_text: Full PRP markdown text
        
    Returns:
        List of target schema definitions
    """
    # Find Section 9 in PRP
    section_9_match = re.search(
        r'## 9\. Target Schema.*?(?=## 10\.|$)',
        prp_text,
        re.DOTALL | re.IGNORECASE
    )
    
    if not section_9_match:
        logger.warning("Could not find Section 9 in PRP")
        return []
    
    section_9_text = section_9_match.group(0)
    
    # Extract table definitions (simplified parsing)
    # In a real implementation, this would be more sophisticated
    target_schemas = []
    
    # Look for table markdown blocks
    table_matches = re.finditer(
        r'### Table: `(.+?)`.*?```(?:json|yaml)?\n(.*?)\n```',
        section_9_text,
        re.DOTALL
    )
    
    for match in table_matches:
        table_name = match.group(1)
        schema_text = match.group(2)
        
        try:
            schema_data = json.loads(schema_text)
            target_schemas.append({
                "table_name": table_name,
                "schema": schema_data
            })
        except json.JSONDecodeError:
            logger.warning(f"Could not parse schema for table: {table_name}")
    
    return target_schemas


# ============================================================================
# SQL Query Workflow (moved from ask_mode_tools.py)
# ============================================================================


async def query_graphql_data(
    operation_name: str,
    variables: Optional[Dict[str, Any]] = None
) -> str:
    """Execute GraphQL query via Apollo MCP server (ACTION MODE).
    
    Args:
        operation_name: Name of the GraphQL operation/tool
        variables: Optional query variables as dictionary
        
    Returns:
        Formatted query results
    """
    try:
        logger.info(f"[ACTION MODE] Executing GraphQL operation: {operation_name}")
        
        if variables is None:
            variables = {}
        
        result = await _apollo_mcp_client.call_tool(operation_name, variables)
        
        # Format results
        return f"# Query Results: {operation_name}\n\n```json\n{json.dumps(result, indent=2)}\n```"
        
    except Exception as e:
        logger.error(f"Error executing GraphQL query: {e}")
        return f"Error executing GraphQL query: {str(e)}"


async def prepare_tables_for_analysis(question: str) -> str:
    """Prepare table information from session state for SQL generation (ACTION MODE - Tool 1/3).
    
    Extracts tables and schemas from the last search_datasets call and stores them in session state
    for use by generate_sql_for_question.
    
    This is the first step in the data analysis workflow:
    1. prepare_tables_for_analysis ← YOU ARE HERE
    2. generate_sql_for_question
    3. execute_sql_query
    
    Args:
        question: The user's question (stored in session for context)
        
    Returns:
        Human-readable status message
    """
    try:
        # Retrieve search results from session state
        search_results = _session_state.get("last_search_results")
        
        if not search_results:
            return "Error: No search results found in session. Please run search_datasets first in Ask Mode to discover tables."
        
        # Extract candidate tables and schemas from search results
        logger.info("[ACTION MODE - Tool 1/3] Extracting tables and schemas from session state")
        try:
            results = search_results.get("results", [])
            original_query = search_results.get("query", "")
            
            if not results:
                return "Error: No tables found in the last search. Please search for datasets first in Ask Mode."
            
            # Extract table IDs and build dataset list
            datasets = []
            for r in results:
                table_id = f"{r['project_id']}.{r['dataset_id']}.{r['table_id']}"
                datasets.append({
                    "table_id": table_id,
                    "project_id": r['project_id'],
                    "dataset_id": r['dataset_id'],
                    "asset_type": r.get('asset_type', 'TABLE'),
                    "schema": r.get("schema", []),
                    "description": r.get("description", ""),
                    "has_pii": r.get('has_pii', False),
                    "has_phi": r.get('has_phi', False),
                })
                logger.info(f"Extracted schema for {table_id}")
            
            logger.info(f"[ACTION MODE - Tool 1/3] Prepared {len(datasets)} tables from search: '{original_query}'")
            logger.info(f"[ACTION MODE - Tool 1/3] Question context: '{question}'")
            
            # Store in session state for next tool
            _session_state["prepared_tables"] = datasets
            _session_state["analysis_question"] = question
            _session_state["original_search_query"] = original_query
            
            # Return human-readable summary
            table_list = "\n".join([f"  - {d['table_id']}" for d in datasets[:5]])
            if len(datasets) > 5:
                table_list += f"\n  ... and {len(datasets) - 5} more"
            
            return f"✓ Successfully prepared {len(datasets)} table(s) for analysis:\n{table_list}\n\nReady for SQL generation."
            
        except KeyError as e:
            return f"Error: Missing required field in search results: {e}"
        
    except Exception as e:
        logger.error(f"Error in prepare_tables_for_analysis: {e}", exc_info=True)
        return f"Error preparing tables: {str(e)}"


async def generate_sql_for_question() -> str:
    """Generate SQL query using query-generation-agent (ACTION MODE - Tool 2/3).
    
    Loads table information from session state (prepared by prepare_tables_for_analysis)
    and generates SQL query. Stores the generated SQL in session state for execute_sql_query.
    
    This is the second step in the data analysis workflow:
    1. prepare_tables_for_analysis
    2. generate_sql_for_question ← YOU ARE HERE
    3. execute_sql_query
    
    Returns:
        Human-readable status with SQL preview
    """
    try:
        if not _query_gen_client:
            return json.dumps({"error": "Query generation client not initialized"})
        
        # Load prepared data from session state
        datasets = _session_state.get("prepared_tables")
        question = _session_state.get("analysis_question")
        
        if not datasets:
            return json.dumps({"error": "No prepared tables found in session. Please run prepare_tables_for_analysis first."})
        
        if not question:
            return json.dumps({"error": "No question found in session. Please run prepare_tables_for_analysis first."})
        
        logger.info(f"[ACTION MODE - Tool 2/3] Generating SQL for {len(datasets)} candidate table(s)")
        
        # Enhance question with guidelines for query generation
        enhanced_question = f"""{question}

QUERY REQUIREMENTS (ACTION MODE):
- LIMIT to 30 rows maximum
- Use latest/most recent data (ORDER BY timestamp/date DESC when applicable)
- Prefer aggregated results (GROUP BY, COUNT, SUM, AVG) unless user explicitly asks for detailed records
- Apply time-based filters for temporal queries (e.g., "last week" should filter by date)"""
        
        # Try each candidate table with retries
        last_result = None
        for dataset in datasets:
            logger.info(f"Attempting SQL generation for table: {dataset['table_id']}")
            for attempt in range(5):
                try:
                    logger.info(f"Query generation attempt {attempt + 1}/5")
                    result = await _query_gen_client.generate_queries(
                        insight=enhanced_question,
                        datasets=[dataset],
                        max_queries=1,
                        max_iterations=3
                    )
                    
                    # Check if we got valid queries
                    if result and "queries" in result and result["queries"]:
                        # Extract the first (and only) query
                        query = result["queries"][0]
                        query_name = query.get("query_name", "unknown")
                        
                        # Initialize session state queries dict if needed
                        if "queries" not in _session_state:
                            _session_state["queries"] = {}
                        
                        # Store full query indexed by query_name
                        _session_state["queries"][query_name] = query
                        
                        logger.info(f"[ACTION MODE - Tool 2/3] Saved query '{query_name}' to session state")
                        logger.info(f"[ACTION MODE - Tool 2/3] Generated SQL successfully for table: {dataset['table_id']}")
                        
                        # Return human-readable summary for the agent
                        summary = _query_gen_client.format_query_summary(result)
                        return summary
                    
                    last_result = result
                    logger.warning(f"No valid queries in result")
                            
                except Exception as e:
                    logger.warning(f"Query generation attempt {attempt + 1} failed: {e}")
                    last_result = {"error": str(e)}
        
        # If we got here, all attempts failed
        if last_result and isinstance(last_result, dict) and "queries" in last_result:
            # Even if all queries failed, return formatted diagnostic
            summary = _query_gen_client.format_query_summary(last_result)
            return summary
        else:
            return json.dumps(last_result or {"error": "Could not generate SQL query after retries"}, indent=2)
        
    except Exception as e:
        logger.error(f"Error in generate_sql_for_question: {e}", exc_info=True)
        return json.dumps({"error": f"Internal error: {str(e)}"}, indent=2)


async def execute_sql_query(query_name: str) -> str:
    """Execute SQL query using BigQuery agent (ACTION MODE - Tool 3/3).
    
    Loads SQL query from session state by query_name and executes it.
    
    This is the third step in the data analysis workflow:
    1. prepare_tables_for_analysis
    2. generate_sql_for_question
    3. execute_sql_query ← YOU ARE HERE
    
    Args:
        query_name: The name of the query to execute (from generate_sql_for_question)
    
    Returns:
        Query results or error message
    """
    try:
        if not _bigquery_agent:
            return "Error: BigQuery agent not initialized"
        
        # Load query from session state by name
        queries = _session_state.get("queries", {})
        if not queries:
            return "Error: No queries found in session. Please run generate_sql_for_question first."
        
        if query_name not in queries:
            available = ", ".join(queries.keys())
            return f"Error: Query '{query_name}' not found in session. Available queries: {available}"
        
        query_data = queries[query_name]
        sql_query = query_data.get("sql")
        description = query_data.get("description", "")
        
        if not sql_query:
            return f"Error: No SQL found for query '{query_name}'"
        
        logger.info(f"[ACTION MODE - Tool 3/3] Executing query: {query_name}")
        logger.info(f"[ACTION MODE - Tool 3/3] Description: {description}")
        logger.info(f"[ACTION MODE - Tool 3/3] SQL: {sql_query[:150]}...")
        
        # Execute SQL via BigQuery client directly
        result = await _execute_sql_with_bigquery_agent(sql_query, description)
        return result
        
    except Exception as e:
        logger.error(f"Error in execute_sql_query: {e}", exc_info=True)
        return f"Error executing SQL: {str(e)}"


async def get_query_context(query_name: str) -> str:
    """Retrieve a previously generated SQL query from session state (ACTION MODE).
    
    This tool allows users to see the SQL query that was used for a previous request.
    Shows the full SQL code, description, and metadata.
    
    Args:
        query_name: The name of the query to retrieve (from generate_sql_for_question)
    
    Returns:
        Formatted string containing the SQL query and metadata
    """
    try:
        # Load queries from session state
        queries = _session_state.get("queries", {})
        
        if not queries:
            return "Error: No queries found in session. No queries have been generated yet."
        
        # If query not found, list available queries
        if query_name not in queries:
            available = "\n".join([f"  - {name}" for name in queries.keys()])
            return f"Error: Query '{query_name}' not found in session.\n\nAvailable queries:\n{available}"
        
        # Retrieve the query data
        query_data = queries[query_name]
        sql_query = query_data.get("sql", "No SQL found")
        description = query_data.get("description", "No description available")
        table_id = query_data.get("target_table_id", "N/A")
        
        # Format the output
        result = f"""Query: {query_name}
Description: {description}
Target Table: {table_id}

SQL:
```sql
{sql_query}
```
"""
        
        logger.info(f"Retrieved query '{query_name}' from session state")
        return result
        
    except Exception as e:
        logger.error(f"Error in get_query_context: {e}", exc_info=True)
        return f"Error retrieving query: {str(e)}"


async def _execute_sql_with_bigquery_agent(sql: str, context: str) -> str:
    """Execute SQL using BigQuery client directly.
    
    Args:
        sql: SQL query to execute
        context: Original user question for context
        
    Returns:
        Formatted query results or error message
    """
    try:
        from google.cloud import bigquery
        import google.auth
        
        logger.info("Executing SQL query directly with BigQuery client")
        
        # Get credentials and create client
        credentials, project = google.auth.default()
        
        # Get project from environment or credentials
        project_id = os.getenv('GCP_PROJECT_ID') or project
        if not project_id:
            return "Error: GCP_PROJECT_ID not configured"
        
        # Create BigQuery client
        client = bigquery.Client(project=project_id, credentials=credentials)
        
        # Execute query in thread pool (BigQuery operations are blocking)
        logger.info(f"Executing query (length: {len(sql)} chars)")
        query_job = await asyncio.to_thread(client.query, sql)
        
        # Wait for results in thread pool
        logger.info("Waiting for query results...")
        results = await asyncio.to_thread(query_job.result)
        
        # Convert to list in thread pool
        rows = await asyncio.to_thread(list, results)
        
        if not rows:
            return f"Query executed successfully but returned 0 rows.\n\nContext: {context}\n\nQuery:\n```sql\n{sql}\n```"
        
        # Get schema information
        field_names = [field.name for field in results.schema]
        
        # Format as a table
        result_text = f"Query Results ({len(rows)} rows):\n\n"
        result_text += f"Context: {context}\n\n"
        
        # Add column headers
        result_text += " | ".join(field_names) + "\n"
        result_text += "-" * (len(" | ".join(field_names))) + "\n"
        
        # Add rows (limit to 30 for readability)
        for row in rows[:30]:
            values = [str(row.get(field, "NULL")) for field in field_names]
            result_text += " | ".join(values) + "\n"
        
        if len(rows) > 30:
            result_text += f"\n... ({len(rows) - 30} more rows not shown)"
        
        # Add statistics
        if query_job.total_bytes_processed:
            bytes_processed_mb = query_job.total_bytes_processed / (1024 * 1024)
            result_text += f"\n\nBytes processed: {bytes_processed_mb:.2f} MB"
        
        logger.info(f"Successfully executed SQL and retrieved {len(rows)} rows")
        return result_text
        
    except Exception as e:
        logger.error(f"Error executing SQL with BigQuery client: {e}", exc_info=True)
        return f"Error executing SQL: {str(e)}\n\nContext: {context}\n\nQuery:\n```sql\n{sql}\n```"


# ============================================================================
# PRP Execution Workflow
# ============================================================================


async def discover_sources_from_prp() -> str:
    """Discover source tables from PRP Section 9 requirements.
    
    Returns:
        Summary of discovered sources with confirmation prompt
    """
    try:
        prp_text = _session_state.get("prp_text")
        if not prp_text:
            return "No PRP found in session. Please generate a PRP first using Planning Mode."
        
        logger.info("Discovering sources from PRP")
        
        # Extract target schemas from PRP
        target_schemas = _extract_target_schemas(prp_text)
        
        if not target_schemas:
            return "Could not extract target schemas from PRP. Please check Section 9 format."
        
        # Discover sources for each target table
        all_discoveries = []
        
        for target in target_schemas:
            result = await _discovery_client.discover_from_prp(
                prp_markdown=prp_text,
                target_schema=target
            )
            all_discoveries.append({
                "target_table": target["table_name"],
                "sources": result.get("sources", []),
                "mappings": result.get("mappings", [])
            })
        
        # Store in state
        _session_state["discovered_datasets"] = all_discoveries
        _session_state["action_step"] = "discovery"
        _session_state["pending_confirmation"] = "discovery"
        
        # Format response
        response = "# Discovery Results 🔍\n\n"
        response += f"Found sources for {len(all_discoveries)} target table(s):\n\n"
        
        for discovery in all_discoveries:
            response += f"## Target: `{discovery['target_table']}`\n"
            response += f"- **Source tables found**: {len(discovery['sources'])}\n"
            
            for source in discovery['sources'][:5]:  # Show first 5
                response += f"  - `{source.get('table_id', 'N/A')}` "
                response += f"(confidence: {source.get('confidence', 0):.0%})\n"
            
            if len(discovery['sources']) > 5:
                response += f"  - ... and {len(discovery['sources']) - 5} more\n"
            response += "\n"
        
        response += "\n**Next Step**: Would you like to proceed with query generation, "
        response += "iterate on the discovery, or cancel?\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Error discovering sources: {e}")
        return f"Error discovering sources: {str(e)}"


async def generate_queries_from_discovery(approve_discovery: bool = True) -> str:
    """Generate SQL queries from discovered datasets.
    
    Args:
        approve_discovery: Whether user approves the discovery results
        
    Returns:
        Summary of generated queries with confirmation prompt
    """
    try:
        if not approve_discovery:
            return "Discovery not approved. Please use `iterate_on_step` to modify the discovery."
        
        discovered_datasets = _session_state.get("discovered_datasets")
        if not discovered_datasets:
            return "No discovered datasets found. Please run discovery first."
        
        prp_text = _session_state.get("prp_text", "")
        
        logger.info("Generating queries from discovery")
        
        # Generate queries for each target table
        all_query_results = []
        
        for discovery in discovered_datasets:
            target_table = discovery["target_table"]
            sources = discovery["sources"]
            
            # Create insight from PRP
            insight = f"Generate queries for target table {target_table} using discovered sources"
            
            # Prepare datasets for query generation
            datasets = [
                {
                    "table_id": source.get("table_id"),
                    "schema": source.get("schema", {}),
                    "description": source.get("description", "")
                }
                for source in sources
            ]
            
            result = await _query_gen_client.generate_queries(
                insight=insight,
                datasets=datasets,
                max_queries=_session_state.get("max_queries_per_target", 3),
                max_iterations=_session_state.get("max_query_iterations", 10)
            )
            
            all_query_results.append({
                "target_table": target_table,
                "queries": result.get("queries", []),
                "validation": result.get("validation", {})
            })
        
        # Store in state
        _session_state["query_results"] = all_query_results
        _session_state["action_step"] = "queries"
        _session_state["pending_confirmation"] = "queries"
        
        # Format response
        response = "# Query Generation Results 🔧\n\n"
        response += f"Generated queries for {len(all_query_results)} target table(s):\n\n"
        
        for result in all_query_results:
            response += f"## Target: `{result['target_table']}`\n"
            response += f"- **Queries generated**: {len(result['queries'])}\n"
            
            validation = result.get("validation", {})
            if validation:
                response += f"- **Validation status**: {validation.get('status', 'unknown')}\n"
            
            # Show first query
            if result['queries']:
                first_query = result['queries'][0]
                response += "\n**Sample Query**:\n"
                response += f"```sql\n{first_query.get('sql', 'N/A')[:300]}...\n```\n"
            response += "\n"
        
        response += "\n**Next Step**: Would you like to proceed with GraphQL API generation, "
        response += "iterate on the queries, or cancel?\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating queries: {e}")
        return f"Error generating queries: {str(e)}"


async def create_graphql_api(
    approve_queries: bool = True,
    project_name: Optional[str] = None
) -> str:
    """Generate GraphQL API from validated queries.
    
    Args:
        approve_queries: Whether user approves the generated queries
        project_name: Name for the GraphQL project
        
    Returns:
        Success message with file paths
    """
    try:
        if not approve_queries:
            return "Queries not approved. Please use `iterate_on_step` to modify the queries."
        
        query_results = _session_state.get("query_results")
        if not query_results:
            return "No query results found. Please generate queries first."
        
        if not project_name:
            project_name = "data_product_api"
        
        logger.info(f"Creating GraphQL API: {project_name}")
        
        # Flatten all queries
        all_queries = []
        for result in query_results:
            for query in result.get("queries", []):
                all_queries.append({
                    "target_table": result["target_table"],
                    "sql": query.get("sql"),
                    "description": query.get("description"),
                    "parameters": query.get("parameters", [])
                })
        
        result = await _graphql_client.generate_graphql_api(
            queries=all_queries,
            project_name=project_name,
            validation_level="moderate"
        )
        
        # Store in state
        output_path = result.get("output_path", "")
        _session_state["graphql_output_path"] = output_path
        _session_state["action_step"] = "complete"
        _session_state["pending_confirmation"] = None
        
        # Format response
        response = "# GraphQL API Generated! 🚀\n\n"
        response += f"**Project Name**: {project_name}\n"
        response += f"**Output Path**: `{output_path}`\n\n"
        
        # Show generated files
        files = result.get("files", [])
        if files:
            response += "## Generated Files\n\n"
            for file in files:
                response += f"- `{file}`\n"
        
        response += "\n**Status**: Data product workflow complete! ✨\n"
        response += "\nYou can now deploy and use your GraphQL API.\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Error creating GraphQL API: {e}")
        return f"Error creating GraphQL API: {str(e)}"


async def iterate_on_step(step_name: str, modifications: str) -> str:
    """Allow user to request modifications to a previous step.
    
    Args:
        step_name: Step to iterate on (discovery, queries, or graphql)
        modifications: User's requested changes
        
    Returns:
        Status message about re-execution
    """
    try:
        logger.info(f"Iterating on step: {step_name}")
        
        valid_steps = ["discovery", "queries", "graphql"]
        if step_name not in valid_steps:
            return f"Invalid step name. Must be one of: {', '.join(valid_steps)}"
        
        # Store modification request
        _session_state[f"{step_name}_modifications"] = modifications
        
        response = f"# Iterating on {step_name.title()} Step 🔄\n\n"
        response += f"**Modifications requested**: {modifications}\n\n"
        
        # Re-execute the appropriate step
        if step_name == "discovery":
            # Clear downstream results
            _session_state.pop("query_results", None)
            _session_state.pop("graphql_output_path", None)
            return response + "\nPlease call `discover_sources_from_prp` again to re-run discovery."
        
        elif step_name == "queries":
            # Clear downstream results
            _session_state.pop("graphql_output_path", None)
            return response + "\nPlease call `generate_queries_from_discovery` again to re-generate queries."
        
        elif step_name == "graphql":
            return response + "\nPlease call `create_graphql_api` again to re-generate the GraphQL API."
        
    except Exception as e:
        logger.error(f"Error iterating on step: {e}")
        return f"Error iterating on step: {str(e)}"

