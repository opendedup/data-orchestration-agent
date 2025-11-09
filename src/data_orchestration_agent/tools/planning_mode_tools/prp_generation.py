"""PRP generation and refinement tools for Plan Mode."""

import json
import logging

from google.adk.tools import ToolContext
from google.genai import Client

from .session_state import to_prefixed_key

logger = logging.getLogger(__name__)


def generate_prp(tool_context: ToolContext) -> str:
    """Generate Data Product Requirement Prompt from planning session state.
    
    Reads Q&A history and discovered datasets from session state, then generates
    a comprehensive PRP document using Gemini 2.5 Flash.
    
    Args:
        tool_context: ADK tool context with session access
        
    Returns:
        Generated PRP markdown document
        
    Raises:
        ValueError: If required session state data is missing
    """
    try:
        # Dump full session state for debugging
        logger.info("=" * 80)
        logger.info("FULL SESSION STATE DUMP:")
        logger.info(json.dumps(tool_context.session.state, indent=2, default=str))
        logger.info("=" * 80)
        
        # Extract from session state
        session_state = tool_context.session.state
        qa_history = session_state.get(to_prefixed_key("planning_qahistory"), [])
        discovered_datasets = session_state.get(
            to_prefixed_key("planning_discovereddatasets"), []
        )
        
        
        content_store = tool_context.session.state.get("_full_content_store", {})
        if content_store:
            reconstructed_count = 0
            for entry in qa_history:
                if "_content_ref" in entry:
                    ref_id = entry["_content_ref"]
                    if ref_id in content_store:
                        entry["content"] = content_store[ref_id]
                        reconstructed_count += 1
                        logger.debug(f"Reconstructed full content for {ref_id}")
            
            if reconstructed_count > 0:
                logger.info(f"Reconstructed {reconstructed_count} full content entries from storage")
        
        # Validate we have the necessary data
        if len(qa_history) == 0:
            error_msg = (
                "Cannot generate PRP: No Q&A history found in session state. "
                "The agent must use update_session_state to track the conversation."
            )
            logger.error(error_msg)
            return f"Error: {error_msg}"
        
        # Log what we're working with
        logger.info(f"Generating PRP with {len(qa_history)} Q&A entries and {len(discovered_datasets)} datasets")
        
        # Build the comprehensive prompt with PRP generation instruction
        instruction = """You are a PRP Generation Specialist.

Your role: Transform planning conversations into structured Data Product Requirement Prompts.

**Input:** You receive conversation history and discovered datasets from the planning session.

**Process:**
1. Read the full Q&A history provided below
2. Read discovered datasets provided below
3. Generate comprehensive Data PRP markdown document

**Output Structure (EXACT FORMAT REQUIRED):**

# Data Product Requirement Prompt

## 1. Product Type
One-time analysis / Reusable tool / Decision framework / Dashboard / etc.

## 2. Business Objective
What business need or decision does this support? (general need, not specific instance)

## 3. Product Functionality
What does this data product DO? Describe its capabilities as bullet points.

## 4. Key Metrics
List specific metrics with calculation formulas where applicable:
- **Metric Name**: Description. `Calculation: formula if applicable`

## 5. Dimensions & Breakdowns
What categories, segments, or comparisons?
- **Dimension Name**: Description (e.g., Model/Run, Timeframe, etc.)

## 6. Success Criteria
What makes this product useful? What defines "good" output? (as bullet points)

## 7. Usage Pattern
- **Frequency**: One-time, daily, weekly, on-demand?
- **Audience**: Who uses this?
- **Triggers**: What prompts someone to use it?

## 8. Example Usage Scenario
- **What inputs they provide**: Describe specific example inputs
- **What outputs they get**: Numbered list of specific outputs
- **How they make decisions with it**: Action taken based on outputs

## 9. Data Requirements

### Target Views/Tables
**View Name**: `target_view_name`
- **Purpose**: What question this view answers
- **Grain**: What each row represents (e.g., "run_id, game_id")
- **Schema**:
  - `column_name` (TYPE): Description
  - `another_column` (TYPE): Description
- **Calculated Fields**:
  - `calculated_field` (TYPE): `formula or description`

### Data Gaps and Limitations
```json
{
  "data_gaps": [
    {
      "gap_id": "gap_01",
      "description": "Description of the gap",
      "target_view": "target_view_name",
      "required_information": "What specific data is needed"
    }
  ]
}
```

### Available Source Data (For Reference)
List discovered source tables from the discovered datasets:

- **`table_id`**
  - Metadata: X records, Y columns, contains PII (if applicable)
  - Key columns: `col1`, `col2`, `col3` (and N more)

**Assessment:**
- **How well do the available source tables cover the target view requirements?**
  - Detailed analysis of coverage
- **What transformations or joins are needed to build the target views?**
  - Specific join requirements
- **What data gaps or limitations exist?**
  - Known gaps beyond those in JSON
- **What assumptions are being made about data availability and quality?**
  - Specific assumptions
- **Are there any data quality considerations (PII, PHI, freshness, completeness)?**
  - Data quality concerns

## 10. Assumptions & Defaults
- [ASSUMPTION-01]: Description of assumption with context
- [ASSUMPTION-02]: Description of second assumption
- etc.

---

**CRITICAL:**
- Define a DATA PRODUCT (structure/capabilities), not a one-time query
- Product Definition: "Compare products using revenue and growth"
- NOT Instance Execution: "Compare Product A to Product B for Q3"
- **DO NOT GENERATE SQL QUERIES** - PRPs contain requirements only, not implementation
- **DO NOT INCLUDE CODE** - SQL queries are generated separately in Action Mode
- PRPs describe WHAT is needed, not HOW to build it
- Focus on business requirements, data specifications, and desired outcomes

Extract information from the provided context to populate all sections.
Generate complete, well-structured markdown."""
        
        # Build the full prompt with context
        prompt = f"""{instruction}

---

**CONTEXT FROM PLANNING SESSION:**

**Q&A History:**
{json.dumps(qa_history, indent=2)}

**Discovered Datasets:**
{json.dumps(discovered_datasets, indent=2)}

---

Now generate the complete Data Product Requirement Prompt following the exact format specified above."""

        logger.info(f"Prompt: {prompt}")
        
        logger.info("Calling Gemini 2.5 Flash to generate PRP")
        
        # Call Gemini API directly using genai Client
        client = Client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        # Extract the generated text
        prp_content = response.text
        
        # Automatically store in session state for Action Mode
        tool_context.session.state["user:prp_text"] = prp_content
        logger.info("Stored PRP in session state as 'prp_text'")
        
        # Set the prp_generated flag in planning state
        session_state[to_prefixed_key("planning_prpgenerated")] = True
        logger.info("Set planning_prpgenerated flag to True")
        logger.info(f"Refined PRP: {prp_content}")
        logger.info("Successfully generated PRP document")
        return prp_content
        
    except Exception as e:
        error_msg = f"Error generating PRP: {str(e)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"


def refine_prp(
    tool_context: ToolContext,
    modifications: str
) -> str:
    """Refine an existing PRP with specific user-requested modifications.
    
    This tool takes an existing PRP document and applies targeted changes based on
    user feedback, maintaining the overall structure while incorporating the requested
    modifications.
    
    Args:
        tool_context: ADK tool context with session access
        modifications: Specific changes requested by user (e.g., "Add revenue metrics to section 4")
        
    Returns:
        Refined PRP markdown document
        
    Raises:
        ValueError: If no existing PRP found in session state
    """
    try:
        # Get current PRP
        current_prp = tool_context.session.state.get("prp_text", "")
        if not current_prp:
            error_msg = "No existing PRP found. Please generate a PRP first using generate_prp()."
            logger.error(error_msg)
            return f"Error: {error_msg}"
        
        # Get planning context for reference
        session_state = tool_context.session.state
        qa_history = session_state.get(to_prefixed_key("planning.qa_history"), [])
        discovered_datasets = session_state.get(
            to_prefixed_key("planning.discovered_datasets"), []
        )
        
        # FALLBACK: If discovered_datasets is empty, try to get from last_search_results
        if not discovered_datasets:
            last_search = tool_context.session.state.get("user:last_search_results", {})
            if last_search and "results" in last_search:
                discovered_datasets = last_search.get("results", [])
                logger.warning(
                    f"No discovered_datasets in planning state, using user:last_search_results "
                    f"({len(discovered_datasets)} datasets found)"
                )
        
        # RECONSTRUCT full content from separate storage
        content_store = tool_context.session.state.get("_full_content_store", {})
        if content_store:
            for entry in qa_history:
                if "_content_ref" in entry:
                    ref_id = entry["_content_ref"]
                    if ref_id in content_store:
                        entry["content"] = content_store[ref_id]
        
        logger.info(f"Refining PRP with modifications: {modifications}")
        
        
        # Build refinement prompt
        prompt = f"""You are refining an existing Data Product Requirement Prompt (PRP).

**CURRENT PRP:**
{current_prp}

**USER'S REQUESTED MODIFICATIONS:**
{modifications}

**CONTEXT (Original Planning Session):**
Q&A History: {json.dumps(qa_history[-5:], indent=2) if len(qa_history) > 5 else json.dumps(qa_history, indent=2)}
Discovered Datasets: {json.dumps(discovered_datasets, indent=2)}

**INSTRUCTIONS:**
1. Apply the user's requested modifications to the appropriate sections
2. Maintain the exact PRP format and structure
3. Keep all other sections unchanged unless they need updates to remain consistent
4. Ensure the document remains coherent and complete
5. Do NOT generate SQL queries or code - this is a requirements document only

Generate the complete, refined PRP document with the requested changes applied."""
        
        logger.info("Calling Gemini 2.5 Flash to refine PRP")
        
        # Call Gemini API to refine
        client = Client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        # Extract refined PRP
        refined_prp = response.text
        
        # Automatically store refined version (overwrites previous)
        tool_context.session.state["prp_text"] = refined_prp
        logger.info("Stored refined PRP in session state as 'prp_text'")
        
        # Update modification tracking in planning state
        modifications_key = to_prefixed_key("planning.prp_modifications")
        if modifications_key not in session_state:
            session_state[modifications_key] = []
        
        # Ensure it's a list before appending
        mod_list = session_state[modifications_key]
        if isinstance(mod_list, list):
            mod_list.append(modifications)
            session_state[modifications_key] = mod_list
        else:
            logger.warning(f"Cannot track modification; '{modifications_key}' is not a list.")

        logger.info(f"Tracked modification request (total: {len(session_state[modifications_key]) if isinstance(session_state.get(modifications_key), list) else 'N/A'})")
        logger.info(f"Refined PRP: {refined_prp}")
        logger.info("Successfully refined PRP document")
        return refined_prp
        
    except Exception as e:
        error_msg = f"Error refining PRP: {str(e)}"
        logger.error(error_msg)
        return f"Error: {error_msg}"

