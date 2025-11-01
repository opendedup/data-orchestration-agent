#!/bin/bash

# Run CLI test for orchestration agent scenarios
# Usage: ./scripts/run_cli_test.sh [scenario_name] [--interactive]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}  Data Orchestration Agent Test${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if poetry is available
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}Error: Poetry is not installed${NC}"
    echo "Please install poetry: https://python-poetry.org/docs/#installation"
    exit 1
fi

# Check if environment is set up
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Creating from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}Created .env file. Please update it with your credentials.${NC}"
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
fi

# Load environment variables from .env file
if [ -f ".env" ]; then
    echo -e "${BLUE}Loading environment variables from .env...${NC}"
    # Export variables from .env (ignoring comments and empty lines)
    set -a  # Automatically export all variables
    source <(grep -v '^#' .env | grep -v '^$' | sed 's/\r$//')
    set +a  # Stop automatically exporting
    echo -e "${GREEN}Environment variables loaded${NC}"
    echo ""
fi

# Parse arguments
INTERACTIVE=false
SCENARIO=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --interactive|-i)
            INTERACTIVE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [SCENARIO]"
            echo ""
            echo "Options:"
            echo "  --interactive, -i    Run in interactive mode"
            echo "  --help, -h          Show this help message"
            echo ""
            echo "Scenarios:"
            echo "  nfl_backtest        Run NFL backtest scenario"
            echo "  simple_discovery    Run simple discovery scenario"
            echo ""
            echo "Examples:"
            echo "  $0 --interactive"
            echo "  $0 nfl_backtest"
            echo "  $0 simple_discovery"
            exit 0
            ;;
        *)
            SCENARIO="$1"
            shift
            ;;
    esac
done

# Install dependencies if needed
echo -e "${BLUE}Installing dependencies...${NC}"
poetry install --quiet

echo ""

# Run the appropriate mode
if [ "$INTERACTIVE" = true ]; then
    echo -e "${GREEN}Starting interactive mode...${NC}"
    echo ""
    poetry run python tests/cli_test_runner.py --interactive
else
    # Determine scenario file
    SCENARIO_FILE=""
    
    if [ -z "$SCENARIO" ]; then
        # Default to NFL backtest
        SCENARIO="nfl_backtest"
    fi
    
    case "$SCENARIO" in
        nfl_backtest)
            SCENARIO_FILE="tests/scenarios/nfl_backtest_scenario.json"
            ;;
        simple_discovery)
            SCENARIO_FILE="tests/scenarios/simple_discovery_scenario.json"
            ;;
        *)
            # Assume it's a direct file path
            SCENARIO_FILE="$SCENARIO"
            ;;
    esac
    
    # Check if scenario file exists
    if [ ! -f "$SCENARIO_FILE" ]; then
        echo -e "${RED}Error: Scenario file not found: $SCENARIO_FILE${NC}"
        echo ""
        echo "Available scenarios:"
        ls -1 tests/scenarios/*.json 2>/dev/null | sed 's/.*\//  - /' || echo "  (none found)"
        exit 1
    fi
    
    echo -e "${GREEN}Running scenario: $SCENARIO_FILE${NC}"
    echo ""
    
    # Create output directory
    mkdir -p test_output
    
    # Run the scenario
    poetry run python tests/cli_test_runner.py --scenario "$SCENARIO_FILE"
    
    EXIT_CODE=$?
    
    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ Test completed successfully!${NC}"
    else
        echo -e "${RED}❌ Test failed with exit code: $EXIT_CODE${NC}"
    fi
    
    exit $EXIT_CODE
fi

