@echo off
echo Building Docker image...
docker build -t telegram-voice-transcriber .

echo Checking for existing container...
for /f %%i in ('docker ps -a -q -f "name=voice-transcriber"') do (
    echo Removing existing container...
    docker rm -f voice-transcriber
)

echo Creating data directory if it doesn't exist...
if not exist "%cd%\data" mkdir "%cd%\data"

echo Starting container...
docker run -d --name voice-transcriber --restart unless-stopped ^
  -v "%cd%\.env:/app/.env" ^
  -v "%cd%\google-credentials.json:/app/google-credentials.json" ^
  -v "%cd%\data:/app/data" ^
  telegram-voice-transcriber

echo.
echo Container started. To view logs, run:
echo docker logs -f voice-transcriber