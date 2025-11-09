"""PRP question generation tools for Plan Mode."""

import json
import logging

from google.adk.tools import ToolContext
from google.genai import Client

from .session_state import to_prefixed_key

logger = logging.getLogger(__name__)


def generate_prp_questions(
    tool_context: ToolContext,
    force_completion_check: bool = False
) -> str:
    """Generate next set of PRP questions OR indicate readiness for PRP generation.
    
    Analyzes session state (qa_history, discovered_datasets) to determine what
    information is still needed for a complete PRP, or confirms sufficient data exists.
    Uses LLM-based analysis to intelligently assess gaps and generate contextual questions.
    
    Args:
        tool_context: ADK tool context with session access
        force_completion_check: If True, evaluates readiness even if normally would ask more
        
    Returns:
        JSON string with structure:
        - status: "questions_needed" | "ready_for_prp" | "error"
        - questions: (if questions_needed) Formatted questions with HTML
        - summary: (if ready_for_prp) Summary of collected information
        - reasoning: Explanation of decision
        
    Examples:
        Result when more questions needed:
        {
            "status": "questions_needed",
            "questions": "**1. What metrics...**\\n<ol type=\\"a\\">...",
            "reasoning": "Missing key metrics and success criteria"
        }
        
        Result when ready:
        {
            "status": "ready_for_prp",
            "summary": "Collected: business objective, 3 metrics, ...",
            "reasoning": "All required PRP sections have sufficient information"
        }
    """
    try:
        # Extract from session state
        session_state = tool_context.session.state
        qa_history_key = to_prefixed_key("planning_qahistory")
        datasets_key = to_prefixed_key("planning_discovereddatasets")
        
        qa_history = session_state.get(qa_history_key, [])
        discovered_datasets = session_state.get(datasets_key, {})
        
        # Log what we retrieved
        logger.info(
            f"generate_prp_questions: discovered_datasets type={type(discovered_datasets)}, "
            f"length={len(discovered_datasets) if isinstance(discovered_datasets, (dict, list)) else 'N/A'}, "
            f"is_empty={not discovered_datasets}"
        )
        
        if isinstance(discovered_datasets, dict):
            logger.debug(f"generate_prp_questions: discovered_datasets keys={list(discovered_datasets.keys())}")
        elif isinstance(discovered_datasets, list):
            logger.warning(
                f"generate_prp_questions: discovered_datasets is a LIST (should be dict!), "
                f"length={len(discovered_datasets)}"
            )
        
        # Check if we have minimum required data
        if not discovered_datasets:
            logger.error("generate_prp_questions: discovered_datasets is empty or falsy - cannot generate questions")
            error_result = {
                "status": "error",
                "message": (
                    "No datasets loaded in session. "
                    "You must call load_dataset_to_session(table_ids=[...]) after search_datasets() "
                    "to load full schemas before calling generate_prp_questions()."
                )
            }
            return json.dumps(error_result, indent=2)
        
        # Log what we're working with
        logger.info(
            f"Analyzing PRP readiness with {len(qa_history)} Q&A entries "
            f"and {len(discovered_datasets)} datasets"
        )
        
        # Build the comprehensive analysis prompt
        instruction = """You are a Query Specification Analyst.

ROLE: Determine if we have enough information to write an unambiguous SQL query. 
FIRST infer what you can from discovered dataset schemas, THEN ask minimal questions 
about gaps you cannot infer.

CRITICAL QUERY SPECIFICATION REQUIREMENTS:

1. **Grain** - What does one row represent?
2. **Metrics** - How are calculated fields derived?
3. **NULL Handling** - How to treat missing values?
4. **Filters** - What data to include/exclude?
5. **Temporal Logic** - Time zones, week/month definitions, data latency
6. **Identity & Joins** - Which keys to use, how to handle identity stitching, shared resources
7. **Data Sources** - Which tables/columns are needed?

DISCOVERED DATASETS (Available Source Data):
{discovered_datasets}

Q&A HISTORY SO FAR:
{qa_history}

FORCE COMPLETION CHECK: {force_completion_check}

ANALYSIS TASK:

STEP 1 - INFER FROM SCHEMAS:
Review discovered datasets and extract what you CAN determine:
- Available columns, data types, descriptions
- Timestamp columns (note: timezone info if present)
- ID/key columns (which look like primary keys, foreign keys)
- Numeric columns (potential metrics)
- Existing filters or partitioning hints
- Table descriptions and examples

STEP 2 - IDENTIFY GAPS:
Only flag as "gaps" what CANNOT be inferred from schemas:
- Business logic for metric calculations (if not documented)
- Which of multiple possible grains the user wants
- How to handle ambiguous cases (multiple IDs, NULL values, etc.)
- Timezone assumptions if timestamps lack timezone info
- Identity stitching logic across tables
- Week/month definitions if using calendar aggregations

STEP 3 - DECIDE:

IF we have enough information to write SQL (after inference) → Return:
{{"status": "ready_for_prp", "summary": "What we know from schema + Q&A", "reasoning": "Why we can write SQL"}}

IF critical gaps remain → Generate 1-2 questions about ONLY what cannot be inferred:
{{"status": "questions_needed", "questions": "Formatted questions", "reasoning": "What's still ambiguous"}}

QUESTION STRATEGY - Maximum Inference, Minimum Questions:
- Reference specific columns/tables from discovered datasets in questions.
- Show what you already know and ask only about ambiguities.
- Combine related ambiguities into single questions.
- **Where possible, provide multiple-choice options based on inferred possibilities from the schema.** This helps guide the user and get precise answers faster.
- Use open-ended questions only when multiple-choice is not feasible.

EXAMPLE EFFICIENT QUESTIONS:

**1. What should one row in your final dataset represent?**
    a) One customer transaction
    b) A daily summary for each product
    c) A complete user journey or session
    d) Other (please specify)

**2. To calculate 'average order value per customer' from the `transactions` table, please clarify:**
    a) Should returned orders be included or excluded from the calculation?
    b) How should guest checkouts (where `customer_id` is NULL) be handled?
    c) Should calculations be based on `order_total` or `order_subtotal`?

**3. The `orders` table has `created_at_utc` and `shipped_at_local` timestamps. For analyzing "monthly sales", which date should define the month?**
    a) `created_at_utc` (based on when the order was placed)
    b) `shipped_at_local` (based on when the order was shipped, using the local timezone)
    c) Other (please specify)

CRITICAL RULES:
- Ask AT MOST 1-3 questions per round
- DON'T ask about things obvious from schema/descriptions
- DO show what you've inferred to build confidence
- Reference actual table/column names from discovered datasets
- Return ONLY valid JSON (no markdown code blocks)

Now analyze and return your JSON decision."""
        
        # Build the full prompt with context
        prompt = instruction.format(
            discovered_datasets=json.dumps(discovered_datasets, indent=2),
            qa_history=json.dumps(qa_history, indent=2),
            force_completion_check=force_completion_check
        )
        
        logger.info("Calling Gemini 2.5 Flash to analyze PRP readiness")
        logger.debug(f"Prompt length: {len(prompt)} characters")
        
        # Call Gemini API to analyze
        client = Client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        # Extract and parse response
        response_text = response.text.strip()
        
        # Clean up response if it contains markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        elif response_text.startswith("```"):
            response_text = response_text.replace("```", "").strip()
        
        # Parse JSON response
        try:
            result = json.loads(response_text)
            logger.info(f"PRP readiness analysis complete: status={result.get('status')}")
            return json.dumps(result, indent=2)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response: {response_text}")
            error_result = {
                "status": "error",
                "message": f"Failed to parse analysis result: {str(e)}",
                "raw_response": response_text[:500]  # Include snippet for debugging
            }
            return json.dumps(error_result, indent=2)
        
    except Exception as e:
        error_msg = f"Error analyzing PRP readiness: {str(e)}"
        logger.error(error_msg)
        error_result = {
            "status": "error",
            "message": error_msg
        }
        return json.dumps(error_result, indent=2)

