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

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_FILE=/app/logs/chatd.log \
    LOG_LEVEL=INFO \
    LOG_MAX_BYTES=10485760 \
    LOG_BACKUP_COUNT=5

# Create log directory
RUN mkdir -p /app/logs

# Copy application code
COPY . /app/

# Set entrypoint
ENTRYPOINT ["python", "main.py"]
