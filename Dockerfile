# Dockerfile
FROM python:3.11-slim

# System basics
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (better cache)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy code and docs
COPY . ./

# Default: run the CLI
ENV PYTHONUNBUFFERED=1
CMD ["python", "app/main.py"]
