#!/bin/bash
# Test script for LangGraph Orchestration Agent
# Make sure the agent is running on port 8085 before running these tests

BASE_URL="http://localhost:8085"

echo "==================================="
echo "Testing LangGraph Orchestration Agent"
echo "==================================="
echo ""

# Test 1: Health check
echo "1. Health Check"
echo "-----------------------------------"
curl -s "${BASE_URL}/health" | jq .
echo ""
echo ""

# Test 2: Basic chat (Ask Mode)
echo "2. Ask Mode - Basic Question"
echo "-----------------------------------"
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hi! Can you help me explore some data?",
    "session_id": "test_session_1"
  }' | jq .
echo ""
echo ""

# Test 3: Search datasets
echo "3. Ask Mode - Search Datasets"
echo "-----------------------------------"
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Search for tables related to sales data",
    "session_id": "test_session_1"
  }' | jq .
echo ""
echo ""

# Test 4: Switch to Plan Mode
echo "4. Switch to Plan Mode"
echo "-----------------------------------"
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Switch to plan mode",
    "session_id": "test_session_2"
  }' | jq .
echo ""
echo ""

# Test 5: Clear session
echo "5. Clear Session"
echo "-----------------------------------"
curl -s -X DELETE "${BASE_URL}/session/test_session_1" | jq .
echo ""
echo ""

# Test 6: Streaming chat (optional - shows first few chunks)
echo "6. Streaming Chat (first 5 seconds)"
echo "-----------------------------------"
timeout 5s curl -s -X POST "${BASE_URL}/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "session_id": "test_session_3"
  }' || true
echo ""
echo ""

echo "==================================="
echo "Testing Complete!"
echo "==================================="

