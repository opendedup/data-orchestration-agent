# =============================================================================
# Data Orchestration Agent - ADK Service Dockerfile
# =============================================================================
# Multi-stage build for optimized container image
# =============================================================================

# Stage 1: Builder
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry for dependency management
RUN pip install --no-cache-dir poetry==1.7.0

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create virtual env (we're in a container)
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --only main --no-interaction --no-ansi

# Stage 2: Runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash adk && \
    chown -R adk:adk /app

# Switch to non-root user
USER adk

# Set Python path
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Set unbuffered Python output for better logging
ENV PYTHONUNBUFFERED=1

# Expose ADK API server port
EXPOSE 8085

# Health check (for container orchestration)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8085/health')" || exit 1

# Default command: run AG-UI server
# Uses the new main.py entry point for AG-UI protocol support
CMD ["python", "-m", "data_orchestration_agent.main", "--host", "0.0.0.0", "--port", "8085"]

# Labels for container metadata
LABEL maintainer="data-orchestration-agent"
LABEL description="ADK orchestration service with AG-UI support for data discovery, planning, and product creation"
LABEL version="1.0.0"

