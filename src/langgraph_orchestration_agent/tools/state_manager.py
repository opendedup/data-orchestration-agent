"""State manager for ask mode session data."""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class AskModeStateManager:
    """Manages session state for ask mode including queries, results, and datasets."""

    def __init__(self, state: dict[str, Any]):
        """Initialize state manager with current state.

        Args:
            state: LangGraph state dictionary
        """
        self.state = state

        # Initialize state fields if they don't exist
        if "queries" not in self.state:
            self.state["queries"] = []
        if "query_results" not in self.state:
            self.state["query_results"] = []
        if "datasets" not in self.state:
            self.state["datasets"] = {}
        if "last_search_results" not in self.state:
            self.state["last_search_results"] = None

    # Query management
    def add_query(
        self, query: str, querysummary: str, question: str
    ) -> int:
        """Add a generated query to history.

        Args:
            query: SQL query string
            querysummary: Human-readable summary of the query
            question: Original question that generated the query

        Returns:
            Index of the added query
        """
        query_entry = {
            "query": query,
            "querysummary": querysummary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "question": question,
        }
        self.state["queries"].append(query_entry)
        logger.info(f"Added query #{len(self.state['queries']) - 1}")
        return len(self.state["queries"]) - 1

    def get_query(self, index: int) -> dict[str, Any] | None:
        """Get a query by index.

        Args:
            index: Query index

        Returns:
            Query entry or None if index is invalid
        """
        queries = self.state["queries"]
        if 0 <= index < len(queries):
            return queries[index]
        return None

    def list_queries(self) -> list[dict[str, Any]]:
        """Get all queries.

        Returns:
            List of all query entries
        """
        return self.state["queries"]

    # Query results management
    def add_result(self, query: str, result: str) -> None:
        """Add a query execution result.

        Args:
            query: SQL query that was executed
            result: Formatted result string
        """
        result_entry = {
            "query": query,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }
        self.state["query_results"].append(result_entry)
        logger.info(f"Added query result #{len(self.state['query_results']) - 1}")

    def get_result(self, index: int) -> dict[str, Any] | None:
        """Get a query result by index.

        Args:
            index: Result index

        Returns:
            Result entry or None if index is invalid
        """
        results = self.state["query_results"]
        if 0 <= index < len(results):
            return results[index]
        return None

    # Dataset management
    def add_dataset(self, table_id: str, details: str) -> None:
        """Add or update dataset metadata.

        Args:
            table_id: Fully qualified table ID
            details: Markdown-formatted dataset details
        """
        dataset_entry = {
            "table_id": table_id,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.state["datasets"][table_id] = dataset_entry
        logger.info(f"Added/updated dataset: {table_id}")

    def get_dataset(self, table_id: str) -> dict[str, Any] | None:
        """Get dataset metadata by table ID.

        Args:
            table_id: Fully qualified table ID

        Returns:
            Dataset entry or None if not found
        """
        return self.state["datasets"].get(table_id)

    # Search results management
    def set_last_search_results(self, results: dict[str, Any]) -> None:
        """Set the last search results.

        Args:
            results: Search results dictionary
        """
        self.state["last_search_results"] = results
        logger.info(
            f"Set last search results: {results.get('total_count', 0)} datasets"
        )

    def get_last_search_results(self) -> dict[str, Any] | None:
        """Get the last search results.

        Returns:
            Last search results or None
        """
        return self.state["last_search_results"]

