# Dockerfile for Lucy 24/7 Agent (Oracle Cloud / VPS Deployment)
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    DEBIAN_FRONTEND=noninteractive

# Install essential Linux utilities and Korean fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    ffmpeg \
    fonts-nanum \
    fontconfig \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . /app/

# Ensure required runtime directories exist
RUN mkdir -p memory keys uploads knowledge workspace

# Expose Web Interface Port
EXPOSE 8765

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8765/ || exit 1

# Start Lucy Web Server by default
CMD ["python", "web.py"]
