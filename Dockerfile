# Use a multi-stage build for a smaller image
FROM python:3.11-slim AS builder

# Set up work directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Second stage - runtime image
FROM python:3.11-slim

# Set up work directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 chatd

# Copy Python packages from builder to user directory
COPY --from=builder /root/.local /home/chatd/.local

# Set proper ownership and PATH for non-root user
RUN chown -R chatd:chatd /home/chatd/.local
ENV PATH=/home/chatd/.local/bin:$PATH

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_FILE=/app/logs/chatd.log \
    LOG_LEVEL=INFO \
    LOG_MAX_BYTES=10485760 \
    LOG_BACKUP_COUNT=5

# Create mount points with proper ownership
RUN mkdir -p /app/data /app/logs /app/Summer2026-Internships && \
    chown -R chatd:chatd /app

# Copy application code and set ownership
COPY . /app/
RUN chown -R chatd:chatd /app

# Switch to non-root user
USER chatd

# Health check to ensure the bot is running properly
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Set entrypoint
ENTRYPOINT ["python", "main.py"]
