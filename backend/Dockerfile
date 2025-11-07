# Use Python 3.9 slim
FROM python:3.9-slim

# Environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements
COPY requirements.txt /app/requirements.txt

# Install dependencies (removed WeasyPrint dependencies - not needed for MCP fork)
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    libpq-dev \
    libffi-dev \
    python3-dev \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && apt-get remove -y gcc build-essential libffi-dev python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

# Use PORT environment variable (Railway requirement)
EXPOSE ${PORT:-8000}

# Use PORT env var for Railway compatibility
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2