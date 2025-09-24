# Multi-stage build to reduce final image size
FROM astral/uv:0.8.19-python3.12-bookworm-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set work directory
WORKDIR /app

# Install build dependencies for native Python packages (madoka, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    python3-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY main.py ./

# Install dependencies using uv (production only)
RUN uv sync --frozen --no-dev

# Production stage
FROM astral/uv:0.8.19-python3.12-bookworm-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set work directory
WORKDIR /app

# Install only runtime dependencies (curl for health check)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire environment from builder
COPY --from=builder /app /app

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application using uv
CMD ["uv", "run", "python", "main.py"]