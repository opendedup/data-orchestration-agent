"""PRP Generator sub-agent for creating Data Product Requirement Prompts."""

from google.adk.agents import Agent

from ..config import Config


def create_prp_generator_agent(config: Config) -> Agent:
    """Create PRP Generator sub-agent that reads from session state.
    
    Args:
        config: Configuration object
        
    Returns:
        Configured PRP Generator sub-agent
    """
    
    instruction = """You are a PRP Generation Specialist.

Your role: Transform planning conversations into structured Data Product Requirement Prompts.

**Input:** You receive conversation history from `ctx.session.state["planning"]["qa_history"]`

**Process:**
1. Read the full Q&A history from session state
2. Read discovered datasets from session state
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
List discovered source tables from session.state["planning"]["discovered_datasets"]:

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

Extract information from session state to populate all sections.
Generate complete, well-structured markdown."""
    
    agent = Agent(
        name="prp_generator",
        model=config.agent_model,
        instruction=instruction,
        tools=[]  # No tools, pure generation based on session state
    )
    
    return agent

