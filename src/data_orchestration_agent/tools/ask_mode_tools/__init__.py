"""Ask Mode tools for data exploration and query execution."""

from typing import Any

from . import search_tools, query_tools, utility_tools

__all__ = [
    "search_tools",
    "query_tools",
    "utility_tools",
    "set_clients",
]


def set_clients(
    discovery_client: Any,
    query_gen_client: Any,
    bigquery_agent: Any
) -> None:
    """Set the global client instances for all ask mode tools.
    
    Args:
        discovery_client: Data discovery client instance
        query_gen_client: Query generation client instance
        bigquery_agent: BigQuery agent instance
    """
    search_tools.set_clients(discovery_client)
    query_tools.set_clients(query_gen_client, bigquery_agent)

