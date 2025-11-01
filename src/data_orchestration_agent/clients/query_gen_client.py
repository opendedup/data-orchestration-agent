"""HTTP client for the Query Generation Agent MCP service."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class QueryGenClient:
    """Client for interacting with the Query Generation Agent via HTTP."""

    def __init__(self, base_url: str, timeout: float = 300.0):
        """Initialize the query generation client.
        
        Args:
            base_url: Base URL for the query generation agent (e.g., http://localhost:8081)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool via HTTP.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool response as dictionary
            
        Raises:
            httpx.HTTPError: If the HTTP request fails
        """
        url = f"{self.base_url}/mcp/call-tool"
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": 1
        }
        
        logger.info(f"Calling query generation tool: {tool_name}")
        logger.debug(f"Request payload: {payload}")
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"Response: {result}")
        
        return result

    async def generate_queries(
        self,
        insight: str,
        datasets: List[Dict[str, Any]],
        max_queries: Optional[int] = None,
        max_iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate SQL queries from insight and discovered datasets.
        
        Args:
            insight: Natural language description of the desired queries
            datasets: List of discovered datasets with schemas
            max_queries: Maximum number of queries to generate
            max_iterations: Maximum iterations for query refinement
            
        Returns:
            Dictionary containing query generation results with structure:
            
            {
                "queries": [
                    {
                        "query_name": "aggregate_by_payment",  # Unique identifier
                        "sql": "SELECT payment_method...",      # The SQL query
                        "description": "Calculate avg...",      # Human description
                        "validation_status": "valid",           # "valid" or "failed"
                        "alignment_score": 0.92,                # 0-1 relevance score
                        "source_tables": ["project.dataset.table"],
                        "iterations": 2,                        # Refinement count
                        "generation_time_ms": 3500.0
                    }
                ],
                "total_attempted": 3,        # Queries tried
                "total_validated": 1,        # Queries succeeded
                "insight": "original question",
                "warnings": ["warning 1"],   # List of warnings
                "failure_diagnostic": "..."  # Present if all failed
            }
            
        Example:
            >>> result = await client.generate_queries(
            ...     insight="What are average sales by region?",
            ...     datasets=[{"table_id": "sales.transactions", ...}]
            ... )
            >>> for query in result["queries"]:
            ...     print(f"SQL: {query['sql']}")
            ...     print(f"Score: {query['alignment_score']}")
        """
        logger.info(f"Generating queries for insight: {insight}")
        arguments = {
            "insight": insight,
            "datasets": datasets
        }
        
        if max_queries is not None:
            arguments["max_queries"] = max_queries
        if max_iterations is not None:
            arguments["max_iterations"] = max_iterations
        
        result = await self._call_tool("generate_queries", arguments)
        response = result.get("result", {})
        
        # Filter out failed queries, only keep valid ones
        all_queries = response.get("queries", [])
        valid_queries = [q for q in all_queries if q.get("validation_status") == "valid"]
        
        total_attempted = len(all_queries)
        total_valid = len(valid_queries)
        
        logger.info(
            f"Query generation complete: {total_valid}/{total_attempted} queries valid"
        )
        
        if total_valid < total_attempted:
            logger.warning(
                f"Filtered out {total_attempted - total_valid} failed query attempts"
            )
        
        # Get best query (highest alignment score, or first if tied)
        if valid_queries:
            best_query = max(valid_queries, key=lambda q: q.get("alignment_score", 0))
            response["queries"] = [best_query]  # Only return the best one
            response["total_validated"] = 1
            logger.info(
                f"Selected best query: {best_query.get('query_name')} "
                f"(alignment: {best_query.get('alignment_score', 0):.2f})"
            )
        else:
            response["queries"] = []
            response["total_validated"] = 0
        
        return response
    
    async def generate_queries_async(
        self,
        insight: str,
        datasets: List[Dict[str, Any]],
        max_queries: Optional[int] = None,
        max_iterations: Optional[int] = None,
        poll_interval: float = 5.0,
        max_wait_seconds: float = 600.0
    ) -> Dict[str, Any]:
        """Generate SQL queries using async endpoint with polling (timeout-safe).
        
        This method uses the async endpoint to avoid HTTP timeouts during long-running
        query generation tasks. Instead of waiting for completion in a single request,
        it starts a task and polls for completion.
        
        Args:
            insight: Natural language description of the desired queries
            datasets: List of discovered datasets with schemas
            max_queries: Maximum number of queries to generate
            max_iterations: Maximum iterations for query refinement
            poll_interval: Seconds between status polls (default: 5)
            max_wait_seconds: Maximum time to wait for completion (default: 600s/10min)
            
        Returns:
            Dictionary containing query generation results (same format as generate_queries)
            
        Raises:
            TimeoutError: If query generation exceeds max_wait_seconds
            httpx.HTTPError: If HTTP requests fail
            
        Example:
            >>> result = await client.generate_queries_async(
            ...     insight="What are average sales by region?",
            ...     datasets=[{"table_id": "sales.transactions", ...}],
            ...     max_wait_seconds=600.0
            ... )
        """
        logger.info(f"Generating queries (async) for insight: {insight}")
        
        arguments = {
            "insight": insight,
            "datasets": datasets
        }
        
        if max_queries is not None:
            arguments["max_queries"] = max_queries
        if max_iterations is not None:
            arguments["max_iterations"] = max_iterations
        
        # Step 1: Start async task
        url = f"{self.base_url}/mcp/call-tool-async"
        
        # Build JSON-RPC 2.0 request
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call_async",
            "params": {
                "name": "generate_queries",
                "arguments": arguments
            },
            "id": 1
        }
        
        logger.info("Starting async query generation task")
        
        # Use shorter timeout for starting task (30s should be plenty)
        start_client = httpx.AsyncClient(timeout=30.0)
        try:
            response = await start_client.post(url, json=payload)
            response.raise_for_status()
            
            task_data = response.json()
            logger.info(f"Received task response: {task_data}")
            
            # Extract result from JSON-RPC response
            # Response format: {"jsonrpc": "2.0", "result": {...}, "id": ...}
            if "result" in task_data:
                result = task_data["result"]
            elif "error" in task_data:
                error = task_data["error"]
                logger.error(f"MCP server returned error: {error}")
                raise ValueError(f"MCP server error: {error.get('message', str(error))}")
            else:
                logger.error(f"Unexpected response format. Full response: {task_data}")
                raise ValueError(f"Unexpected MCP response format. Keys: {list(task_data.keys())}")
            
            # Extract task_id from result
            if "task_id" not in result:
                logger.error(f"No task_id in result. Full result: {result}")
                raise ValueError(
                    f"MCP server result missing 'task_id'. Result keys: {list(result.keys())}. "
                    f"This may indicate the MCP server doesn't support async operations correctly."
                )
            
            task_id = result["task_id"]
            logger.info(f"Task started: {task_id}")
        finally:
            await start_client.aclose()
        
        # Step 2: Poll for completion
        start_time = time.time()
        poll_client = httpx.AsyncClient(timeout=30.0)  # 30s timeout per poll
        
        try:
            while True:
                elapsed = time.time() - start_time
                
                # Check if we've exceeded max wait time
                if elapsed > max_wait_seconds:
                    logger.error(f"Query generation timed out after {max_wait_seconds}s")
                    raise TimeoutError(
                        f"Query generation exceeded maximum wait time of {max_wait_seconds}s "
                        f"({max_wait_seconds/60:.1f} minutes). Task ID: {task_id}"
                    )
                
                # Check task status
                status_url = f"{self.base_url}/mcp/tasks/{task_id}"
                status_response = await poll_client.get(status_url)
                status_response.raise_for_status()
                status_data = status_response.json()
                
                # Check if completed
                if status_data["status"] == "completed":
                    logger.info(f"Task completed after {elapsed:.1f}s")
                    
                    # Fetch result
                    result_url = f"{self.base_url}/mcp/tasks/{task_id}/result"
                    result_response = await poll_client.get(result_url)
                    result_response.raise_for_status()
                    result_data = result_response.json()
                    
                    # Extract the actual result
                    response = result_data.get("result", result_data)
                    break
                
                # Check if failed
                elif status_data["status"] == "failed":
                    error = status_data.get("error", "Unknown error")
                    logger.error(f"Query generation failed on server: {error}")
                    raise RuntimeError(f"Query generation failed: {error}")
                
                # Still running or pending - wait and poll again
                logger.debug(f"Task status: {status_data['status']}, elapsed: {elapsed:.1f}s")
                await asyncio.sleep(poll_interval)
                
        finally:
            await poll_client.aclose()
        
        # Process results (same as original generate_queries)
        all_queries = response.get("queries", [])
        valid_queries = [q for q in all_queries if q.get("validation_status") == "valid"]
        
        total_attempted = len(all_queries)
        total_valid = len(valid_queries)
        
        logger.info(
            f"Query generation complete: {total_valid}/{total_attempted} queries valid"
        )
        
        if total_valid < total_attempted:
            logger.warning(
                f"Filtered out {total_attempted - total_valid} failed query attempts"
            )
        
        # Get best query (highest alignment score, or first if tied)
        if valid_queries:
            best_query = max(valid_queries, key=lambda q: q.get("alignment_score", 0))
            response["queries"] = [best_query]  # Only return the best one
            response["total_validated"] = 1
            logger.info(
                f"Selected best query: {best_query.get('query_name')} "
                f"(alignment: {best_query.get('alignment_score', 0):.2f})"
            )
        else:
            response["queries"] = []
            response["total_validated"] = 0
        
        return response
    
    def format_query_summary(self, result: Dict[str, Any]) -> str:
        """Format query generation results into human-readable summary for agents.
        
        Args:
            result: Result from generate_queries()
            
        Returns:
            Human-readable markdown summary string
        """
        queries = result.get("queries", [])
        total_attempted = result.get("total_attempted", 0)
        total_validated = result.get("total_validated", 0)
        insight = result.get("insight", "")
        warnings = result.get("warnings", [])
        failure_diagnostic = result.get("failure_diagnostic")
        
        lines = [
            "# Query Generation Summary",
            "",
            f"**Insight**: {insight}",
            f"**Status**: {total_validated}/{total_attempted} queries succeeded",
            ""
        ]
        
        if queries:
            # Since we now only return the best query
            query = queries[0]
            lines.append("## Best Generated Query")
            lines.append("")
            lines.append(f"**Query Name**: {query.get('query_name', 'unnamed')}")
            lines.append(f"**Description**: {query.get('description', 'N/A')}")
            lines.append(f"**Alignment Score**: {query.get('alignment_score', 0):.2f}/1.0")
            lines.append(f"**Tables Used**: {', '.join(query.get('source_tables', []))}")
            lines.append(f"**Refinement Iterations**: {query.get('iterations', 0)}")
            lines.append("")
            lines.append("**SQL:**")
            lines.append("```sql")
            lines.append(query.get('sql', ''))
            lines.append("```")
            lines.append("")
        else:
            lines.append("## No Valid Queries Generated")
            lines.append("")
            
            if failure_diagnostic:
                lines.append("### Failure Analysis")
                lines.append(failure_diagnostic)
            
        if warnings:
            lines.append("## Warnings")
            for warning in warnings:
                lines.append(f"- {warning}")
            lines.append("")
        
        return "\n".join(lines)
    
    def extract_best_sql(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract the best SQL query from results.
        
        Args:
            result: Result from generate_queries()
            
        Returns:
            Dictionary with 'sql', 'description', 'alignment_score', and 'tables',
            or None if no valid queries were generated
        """
        queries = result.get("queries", [])
        if not queries:
            return None
        
        # Get query with highest alignment score
        best_query = max(queries, key=lambda q: q.get("alignment_score", 0))
        
        return {
            "sql": best_query.get("sql"),
            "description": best_query.get("description"),
            "alignment_score": best_query.get("alignment_score"),
            "tables": best_query.get("source_tables", [])
        }

