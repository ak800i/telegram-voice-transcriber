FROM python:3.11-slim

# Install required system dependencies for ffmpeg and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create data directory for SQLite database with proper permissions
RUN mkdir -p /app/data && chmod 777 /app/data

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .
RUN chmod +x /app/entrypoint.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Add a script to verify environment variables at runtime
RUN echo '#!/bin/bash\necho "Container environment:"\nls -la .\necho "Environment variables:"\nenv | grep -E "TOKEN|CREDENTIALS"\necho "Content of .env file:"\nif [ -f .env ]; then cat .env; else echo ".env file not found"; fi\necho "Starting bot..."\nexec "$@"' > /entrypoint.sh \
    && chmod +x /entrypoint.sh

# Use the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "main.py"]