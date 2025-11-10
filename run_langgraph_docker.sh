#!/bin/bash
# Quick script to build and run the LangGraph orchestration agent in Docker

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="langgraph-orchestration-agent"
CONTAINER_NAME="langgraph-orchestration-agent"
PORT=8085

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}LangGraph Orchestration Agent - Docker Runner${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo -e "${YELLOW}Please create .env file from .env.example:${NC}"
    echo "  cp .env.example .env"
    echo "  # Then edit .env with your credentials"
    exit 1
fi

# Check if required env vars are set
source .env
if [ -z "$GCP_PROJECT_ID" ] || [ -z "$GOOGLE_API_KEY" ]; then
    echo -e "${RED}Error: Required environment variables not set!${NC}"
    echo -e "${YELLOW}Please set GCP_PROJECT_ID and GOOGLE_API_KEY in .env${NC}"
    exit 1
fi

# Parse command line arguments
ACTION=${1:-run}

case $ACTION in
    build)
        echo -e "${GREEN}Building Docker image...${NC}"
        docker build -f Dockerfile.langgraph -t ${IMAGE_NAME}:latest .
        echo -e "${GREEN}✓ Build complete!${NC}"
        ;;
        
    run)
        echo -e "${GREEN}Building and starting container...${NC}"
        
        # Stop and remove existing container if it exists
        if [ "$(docker ps -aq -f name=${CONTAINER_NAME})" ]; then
            echo -e "${YELLOW}Stopping existing container...${NC}"
            docker stop ${CONTAINER_NAME} 2>/dev/null || true
            docker rm ${CONTAINER_NAME} 2>/dev/null || true
        fi
        
        # Build image
        docker build -f Dockerfile.langgraph -t ${IMAGE_NAME}:latest .
        
        # Run container
        echo -e "${GREEN}Starting container on port ${PORT}...${NC}"
        docker run -d \
            --name ${CONTAINER_NAME} \
            -p ${PORT}:${PORT} \
            --env-file .env \
            -e AGENT_HOST=0.0.0.0 \
            -e AGENT_PORT=${PORT} \
            -e DISCOVERY_AGENT_URL=${DISCOVERY_AGENT_URL:-http://host.docker.internal:8080} \
            -e QUERY_GEN_AGENT_URL=${QUERY_GEN_AGENT_URL:-http://host.docker.internal:8081} \
            -e GRAPHQL_AGENT_URL=${GRAPHQL_AGENT_URL:-http://host.docker.internal:8083} \
            ${IMAGE_NAME}:latest
        
        echo ""
        echo -e "${GREEN}✓ Container started successfully!${NC}"
        echo ""
        echo -e "${BLUE}Container Information:${NC}"
        echo "  Name: ${CONTAINER_NAME}"
        echo "  Port: http://localhost:${PORT}"
        echo ""
        echo -e "${BLUE}Quick Commands:${NC}"
        echo "  View logs:    docker logs -f ${CONTAINER_NAME}"
        echo "  Health check: curl http://localhost:${PORT}/health"
        echo "  Stop:         docker stop ${CONTAINER_NAME}"
        echo "  Shell:        docker exec -it ${CONTAINER_NAME} bash"
        echo ""
        
        # Wait a moment for container to start
        echo -e "${YELLOW}Waiting for container to be ready...${NC}"
        sleep 3
        
        # Test health endpoint
        if curl -s http://localhost:${PORT}/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Health check passed!${NC}"
            curl http://localhost:${PORT}/health | jq .
        else
            echo -e "${YELLOW}⚠ Health check failed - container may still be starting${NC}"
            echo -e "${YELLOW}Check logs with: docker logs ${CONTAINER_NAME}${NC}"
        fi
        ;;
        
    stop)
        echo -e "${YELLOW}Stopping container...${NC}"
        docker stop ${CONTAINER_NAME}
        docker rm ${CONTAINER_NAME}
        echo -e "${GREEN}✓ Container stopped and removed${NC}"
        ;;
        
    logs)
        echo -e "${BLUE}Showing container logs (Ctrl+C to exit):${NC}"
        docker logs -f ${CONTAINER_NAME}
        ;;
        
    shell)
        echo -e "${BLUE}Opening shell in container...${NC}"
        docker exec -it ${CONTAINER_NAME} bash
        ;;
        
    restart)
        echo -e "${YELLOW}Restarting container...${NC}"
        docker restart ${CONTAINER_NAME}
        echo -e "${GREEN}✓ Container restarted${NC}"
        ;;
        
    test)
        echo -e "${BLUE}Testing LangGraph agent...${NC}"
        echo ""
        
        # Health check
        echo -e "${GREEN}1. Health Check:${NC}"
        curl -s http://localhost:${PORT}/health | jq .
        echo ""
        
        # Simple chat
        echo -e "${GREEN}2. Simple Chat:${NC}"
        curl -s -X POST http://localhost:${PORT}/chat \
            -H "Content-Type: application/json" \
            -d '{"message": "Hello!", "session_id": "test"}' | jq .
        echo ""
        ;;
        
    compose)
        echo -e "${GREEN}Starting with Docker Compose...${NC}"
        docker-compose -f docker-compose.langgraph.yml up --build
        ;;
        
    clean)
        echo -e "${YELLOW}Cleaning up...${NC}"
        docker stop ${CONTAINER_NAME} 2>/dev/null || true
        docker rm ${CONTAINER_NAME} 2>/dev/null || true
        docker rmi ${IMAGE_NAME}:latest 2>/dev/null || true
        echo -e "${GREEN}✓ Cleanup complete${NC}"
        ;;
        
    *)
        echo -e "${RED}Unknown action: $ACTION${NC}"
        echo ""
        echo "Usage: $0 [action]"
        echo ""
        echo "Actions:"
        echo "  build    - Build Docker image only"
        echo "  run      - Build and run container (default)"
        echo "  stop     - Stop and remove container"
        echo "  restart  - Restart container"
        echo "  logs     - Show container logs"
        echo "  shell    - Open shell in container"
        echo "  test     - Run basic tests against container"
        echo "  compose  - Run with Docker Compose"
        echo "  clean    - Stop container and remove image"
        echo ""
        exit 1
        ;;
esac

