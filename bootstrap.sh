#!/usr/bin/env bash
set -euo pipefail

# This script provisions Redis via Docker and starts the FastAPI server with hot reload.

if ! command -v docker &>/dev/null; then
  echo "Docker is required but not installed. Aborting." >&2
  exit 1
fi

# 1. Start Redis (detach if not already running)
if ! docker ps --format '{{.Names}}' | grep -q '^namecheck-redis$'; then
  docker run -d --name namecheck-redis -p 6379:6379 redis:7-alpine
fi

# 2. Build the app image
IMAGE_TAG="namecheck-app:local"
docker build -t "$IMAGE_TAG" .

# 3. Run the container

docker run --rm -it \
  --name namecheck-app \
  -p 8000:8000 \
  -e OPENAI_API_KEY=${OPENAI_API_KEY:-} \
  --link namecheck-redis:redis \
  "$IMAGE_TAG" 