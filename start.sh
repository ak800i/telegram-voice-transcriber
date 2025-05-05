#!/bin/bash

# Build the Docker image
docker build -t telegram-voice-transcriber .

# Check if container exists and remove it
if [ "$(docker ps -a -q -f name=voice-transcriber)" ]; then
  echo "Removing existing container..."
  docker rm -f voice-transcriber
fi

# Create data directory if it doesn't exist
mkdir -p "$(pwd)/data"

# Run the Docker container
docker run -d --name voice-transcriber --restart unless-stopped \
  -v "$(pwd)/.env:/app/.env" \
  -v "$(pwd)/$(grep GOOGLE_APPLICATION_CREDENTIALS .env | cut -d= -f2):/app/$(basename $(grep GOOGLE_APPLICATION_CREDENTIALS .env | cut -d= -f2))" \
  -v "$(pwd)/data:/app/data" \
  telegram-voice-transcriber

# Show logs
echo "Container started. To view logs, run:"
echo "docker logs -f voice-transcriber"