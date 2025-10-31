"""Example usage of QueryGenClient with new helper methods."""

import asyncio
from data_orchestration_agent.clients.query_gen_client import QueryGenClient


async def main() -> None:
    """Demonstrate the new QueryGenClient helper methods."""
    
    # Initialize client
    client = QueryGenClient(base_url="http://localhost:8081")
    
    try:
        # Sample datasets
        datasets = [
            {
                "table_id": "lennyisagoodboy.lfndata.game_stats",
                "description": "NFL game statistics with scores and team info",
                "columns": [
                    {"name": "game_id", "type": "STRING"},
                    {"name": "home_team", "type": "STRING"},
                    {"name": "away_team", "type": "STRING"},
                    {"name": "home_score", "type": "INTEGER"},
                    {"name": "away_score", "type": "INTEGER"},
                ]
            }
        ]
        
        # Generate queries
        print("Generating queries...")
        result = await client.generate_queries(
            insight="Show the average score for home and away teams",
            datasets=datasets,
            max_queries=2,
            max_iterations=3
        )
        
        print("\n" + "="*80)
        print("1. RAW RESULT (filtered to only valid queries)")
        print("="*80)
        print(f"Total Attempted: {result['total_attempted']}")
        print(f"Total Validated: {result['total_validated']}")
        print(f"Number of queries: {len(result['queries'])}")
        
        print("\n" + "="*80)
        print("2. FORMATTED SUMMARY (for LLM agents)")
        print("="*80)
        summary = client.format_query_summary(result)
        print(summary)
        
        print("\n" + "="*80)
        print("3. EXTRACT BEST SQL (for execution)")
        print("="*80)
        best_sql = client.extract_best_sql(result)
        if best_sql:
            print(f"Description: {best_sql['description']}")
            print(f"Alignment Score: {best_sql['alignment_score']:.2f}")
            print(f"Tables Used: {', '.join(best_sql['tables'])}")
            print(f"\nSQL:\n{best_sql['sql']}")
        else:
            print("No valid queries generated")
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

