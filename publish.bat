@echo off
echo ===================================================
echo Publishing Telegram Voice Transcriber Docker Image
echo ===================================================
echo.

echo Building latest version of the Docker image...
docker build -t telegram-voice-transcriber .
if %ERRORLEVEL% neq 0 (
    echo Error building Docker image!
    exit /b %ERRORLEVEL%
)

echo.
echo Tagging Docker image as belgradebc/telegram-voice-transcriber:latest
docker tag telegram-voice-transcriber belgradebc/telegram-voice-transcriber:latest
if %ERRORLEVEL% neq 0 (
    echo Error tagging Docker image!
    exit /b %ERRORLEVEL%
)

echo.
echo Logging in to Docker Hub...
echo Please enter your Docker Hub credentials when prompted:
docker login
if %ERRORLEVEL% neq 0 (
    echo Failed to log in to Docker Hub!
    exit /b %ERRORLEVEL%
)

echo.
echo Pushing image to Docker Hub...
docker push belgradebc/telegram-voice-transcriber:latest
if %ERRORLEVEL% neq 0 (
    echo Error pushing Docker image!
    exit /b %ERRORLEVEL%
)

echo.
echo ===================================================
echo Successfully published to Docker Hub as:
echo belgradebc/telegram-voice-transcriber:latest
echo ===================================================
echo.
echo You can pull this image on your NAS using:
echo docker pull belgradebc/telegram-voice-transcriber:latest
echo.
echo Or by running docker-compose with the correct image name
echo in your docker-compose.yml file.