# Telegram Voice Message Transcriber Bot

A Telegram bot that transcribes voice messages to text, specifically optimized for Serbian language.
Tested working with WhatsApp voices on Android (via 3-dot menu > Share).

## Features

- Transcribes voice messages sent to the bot
- Supports Serbian language
- Runs in a Docker container for easy deployment
- Uses Google Cloud Speech-to-Text API for high-quality transcription
- If you want to use Azure's Whisper API, or a local Whiser model, you can find a working implementation in the commit history.

## Prerequisites

- Docker installed on your system
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- A Google Cloud account with Speech-to-Text API enabled
- Google Cloud service account JSON credentials file

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command and follow the instructions to create a new bot
3. Save the bot token provided by BotFather

### 2. Set Up Google Cloud Speech-to-Text API

1. Create a [Google Cloud Project](https://console.cloud.google.com/)
2. Enable the [Speech-to-Text API](https://console.cloud.google.com/apis/library/speech.googleapis.com)
3. Create a service account and download the JSON credentials file

### 3. Configure Environment Variables

1. Create a `.env` file based on the provided [.env.example](/.env.example)

### 4. Build and Run with Docker

To build and run use [start.bat](/start.bat)

## Usage

1. Open Telegram and search for your bot by username
2. Start a conversation with the bot by sending `/start`
3. Send or forward voice messages to the bot
4. The bot will reply with the transcribed text

## Development

If you want to run the bot locally for development:

1. Install Python 3.13+ and the required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up the environment variables in a `.env` file

3. Run the bot:
   ```bash
   python main.py
   ```

## License

MIT
