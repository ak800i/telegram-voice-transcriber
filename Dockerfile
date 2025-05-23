FROM python:3.13-alpine

# Install required system dependencies for ffmpeg and audio processing
RUN apk add --no-cache ffmpeg

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

# Use the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "main.py"]