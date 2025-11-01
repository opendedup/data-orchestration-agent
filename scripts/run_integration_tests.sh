#!/bin/bash

# Run pytest-based integration tests
# Usage: ./scripts/run_integration_tests.sh [options]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}  Integration Tests${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if poetry is available
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}Error: Poetry is not installed${NC}"
    echo "Please install poetry: https://python-poetry.org/docs/#installation"
    exit 1
fi

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo -e "${BLUE}Loading environment variables from .env...${NC}"
    # Export variables from .env (ignoring comments and empty lines)
    set -a  # Automatically export all variables
    source <(grep -v '^#' .env | grep -v '^$' | sed 's/\r$//')
    set +a  # Stop automatically exporting
    echo -e "${GREEN}Environment variables loaded${NC}"
    echo ""
fi

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
poetry install --quiet

echo ""
echo -e "${GREEN}Running integration tests...${NC}"
echo ""

# Run pytest with coverage
poetry run pytest tests/integration/test_orchestration_scenarios.py \
    -v \
    --cov=data_orchestration_agent \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    "$@"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "Coverage report saved to: htmlcov/index.html"
else
    echo -e "${RED}❌ Some tests failed${NC}"
fi

exit $EXIT_CODE

