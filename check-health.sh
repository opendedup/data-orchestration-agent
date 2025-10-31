#!/bin/bash
# =============================================================================
# MCP Agents Health Check Script
# =============================================================================
# Checks the health status of all MCP agents
# =============================================================================

echo "🔍 Checking MCP Agent Health..."
echo ""

# Define agents with their names and ports
agents=(
    "Data Discovery:8080"
    "Query Generation:8081"
    "Data Planning:8082"
    "Data GraphQL:8083"
)

all_healthy=true

# Check each agent
for agent in "${agents[@]}"; do
    name="${agent%%:*}"
    port="${agent##*:}"
    
    if response=$(curl -s -f "http://localhost:${port}/health" 2>/dev/null); then
        status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        if [ "$status" = "healthy" ]; then
            echo "✅ ${name} (port ${port}): healthy"
        else
            echo "⚠️  ${name} (port ${port}): ${status}"
            all_healthy=false
        fi
    else
        echo "❌ ${name} (port ${port}): not responding"
        all_healthy=false
    fi
done

echo ""
echo "📊 Container Status:"
docker compose ps

echo ""
if [ "$all_healthy" = true ]; then
    echo "🎉 All agents are healthy!"
    exit 0
else
    echo "⚠️  Some agents are not healthy or not responding"
    exit 1
fi

