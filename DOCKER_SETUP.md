# MCP Agents - Docker Orchestration

This directory contains the master Docker Compose configuration for running all MCP agents together during development.

## 🔐 Prerequisites - Google Cloud Authentication

**IMPORTANT**: Before starting the agents, you must configure Google Cloud authentication on your host machine.

### Setup Google Cloud Credentials

All agents require Google Cloud authentication to access GCP services (BigQuery, Vertex AI, GCS, etc.). 

**Option 1: Application Default Credentials (Recommended for Local Development)**

Run this command on your host machine:
```bash
gcloud auth application-default login
```

This creates credentials at `~/.config/gcloud/application_default_credentials.json`, which are automatically mounted into all containers.

**Option 2: Service Account Key**

If you prefer using a service account:

1. Create and download a service account key from GCP Console
2. Save it locally (e.g., `~/gcp-keys/service-account.json`)
3. Update the volume mounts in `docker compose.yml` for each agent:
   ```yaml
   volumes:
     - ~/gcp-keys/service-account.json:/app/credentials/service-account.json:ro
   environment:
     - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/service-account.json
   ```

### Credential Mounting in docker compose.yml

The `docker compose.yml` is already configured to mount your gcloud credentials:

- **data-discovery-agent**: `~/.config/gcloud:/home/mcp/.config/gcloud:ro`
- **query-generation-agent**: `~/.config/gcloud:/home/appuser/.config/gcloud:ro`
- **data-planning-agent**: `~/.config/gcloud:/home/mcp/.config/gcloud:ro`
- **data-graphql-agent**: `~/.config/gcloud:/home/mcp/.config/gcloud:ro`

Each agent also has `GOOGLE_APPLICATION_CREDENTIALS` environment variable set to point to the mounted credentials.

### Verify Authentication

After starting the agents, verify authentication is working:
```bash
# Check logs for authentication errors
docker compose logs | grep -i "permission\|auth\|403"

# Should return empty if authentication is working
```

## 🏗️ Architecture

```
data-orchestration-agent/
├── docker compose.yml      # Master orchestration file
├── check-health.sh         # Health check script
└── DOCKER_SETUP.md        # This file

Orchestrates:
├── data-discovery-agent    (port 8080)
├── query-generation-agent  (port 8081)
├── data-planning-agent     (port 8082)
└── data-graphql-agent      (port 8083)
```

All agents communicate via the shared `mcp-platform-network`.

## 🚀 Quick Start

### Start All Agents
```bash
cd /home/user/git/data-orchestration-agent
docker compose up -d
```

### Check Health
```bash
./check-health.sh
```

Expected output:
```
🔍 Checking MCP Agent Health...

✅ Data Discovery (port 8080): healthy
✅ Query Generation (port 8081): healthy
✅ Data Planning (port 8082): healthy
✅ Data GraphQL (port 8083): healthy

📊 Container Status:
...
🎉 All agents are healthy!
```

### View Logs
```bash
# All agents
docker compose logs -f

# Specific agent
docker compose logs -f data-discovery-agent
docker compose logs -f query-generation-agent
docker compose logs -f data-planning-agent
docker compose logs -f data-graphql-agent
```

### Stop All Agents
```bash
docker compose down
```

## 📋 Common Commands

### Start Specific Agents
```bash
# Start only discovery and query generation
docker compose up -d data-discovery-agent query-generation-agent

# Start only planning
docker compose up -d data-planning-agent
```

### Rebuild After Code Changes
```bash
# Rebuild all
docker compose up -d --build

# Rebuild specific agent
docker compose up -d --build data-discovery-agent
```

### Check Container Status
```bash
docker compose ps
```

### Follow Logs in Real-time
```bash
docker compose logs -f
```

### Restart a Specific Agent
```bash
docker compose restart query-generation-agent
```

### Stop Without Removing Containers
```bash
docker compose stop
```

### Start Stopped Containers
```bash
docker compose start
```

## 🔍 Health Endpoints

Each agent exposes a health endpoint:

- Data Discovery: http://localhost:8080/health
- Query Generation: http://localhost:8081/health
- Data Planning: http://localhost:8082/health
- Data GraphQL: http://localhost:8083/health

Test manually:
```bash
curl http://localhost:8080/health
curl http://localhost:8081/health
curl http://localhost:8082/health
curl http://localhost:8083/health
```

## 🌐 Service Discovery

Agents can communicate with each other using container names:

```python
# From any agent, call another agent
import httpx

# Call data-discovery-agent
response = httpx.get("http://data-discovery-agent:8080/health")

# Call query-generation-agent
response = httpx.get("http://query-generation-agent:8081/health")

# Call data-planning-agent
response = httpx.get("http://data-planning-agent:8082/health")

# Call data-graphql-agent
response = httpx.get("http://data-graphql-agent:8083/health")
```

## 📁 Volume Mounts

Each agent has persistent volumes for development:

- **data-discovery-agent**: 
  - `src/` (read-only for live code reload)
  - `config/` (read-only)
  
- **query-generation-agent**: 
  - `logs/` (for query generation logs)
  
- **data-planning-agent**: 
  - `output/` (for generated PRPs)
  - `context.example/` (read-only)
  
- **data-graphql-agent**: 
  - `output/` (for generated GraphQL servers)

## 🔧 Troubleshooting

### Authentication Errors (403 Insufficient Scopes)

If you see errors like `403 Request had insufficient authentication scopes`:

```bash
# 1. Verify gcloud credentials exist on host
ls -la ~/.config/gcloud/application_default_credentials.json

# 2. If missing, run gcloud auth
gcloud auth application-default login

# 3. Restart all containers
docker compose down
docker compose up -d

# 4. Check logs for auth errors
docker compose logs | grep -i "403\|permission\|auth"
```

### Agent Not Starting
```bash
# Check logs for the specific agent
docker compose logs data-discovery-agent

# Check if .env file exists
ls -la ../data-discovery-agent/.env
```

### Port Already in Use
```bash
# Check what's using the port
lsof -i :8080
lsof -i :8081
lsof -i :8082
lsof -i :8083

# Or kill the container using the port
docker ps
docker stop <container_id>
```

### Network Issues
```bash
# Recreate the network
docker compose down
docker network rm mcp-platform-network
docker compose up -d
```

### Clear Everything and Start Fresh
```bash
# Stop and remove all containers, networks, and volumes
docker compose down -v

# Rebuild and start
docker compose up -d --build
```

## 📊 Resource Usage

Check resource usage of all agents:
```bash
docker stats data-discovery-mcp query-generation-mcp data-planning-mcp data-graphql-mcp
```

## 🎯 Development Workflow

### Typical Development Session
```bash
# 1. Start all agents
cd /home/user/git/data-orchestration-agent
docker compose up -d

# 2. Wait for startup
sleep 15

# 3. Check health
./check-health.sh

# 4. Make code changes in any agent directory
# Changes to mounted volumes (src/) are reflected immediately

# 5. View logs to debug
docker compose logs -f data-planning-agent

# 6. Restart specific agent if needed
docker compose restart data-planning-agent

# 7. When done
docker compose down
```

### Testing Inter-Agent Communication
```bash
# Start all agents
docker compose up -d

# Test the full workflow:
# 1. Plan with planning agent (port 8082)
# 2. Discover data with discovery agent (port 8080)
# 3. Generate queries with query-gen agent (port 8081)
# 4. Generate GraphQL with graphql agent (port 8083)
```

## 🆘 Getting Help

- Check individual agent logs: `docker compose logs <service-name>`
- Check health endpoints: `./check-health.sh`
- Verify .env files exist in each agent directory
- Ensure Docker daemon is running: `docker ps`
- Check network connectivity: `docker network inspect mcp-platform-network`

## 📝 Notes

- No resource limits in development for maximum flexibility
- Health checks run every 30 seconds
- All agents restart automatically unless stopped
- Shared network allows seamless inter-agent communication
- Volume mounts enable live code reloading (for mounted src directories)

