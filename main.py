#!/usr/bin/env python
import os
import logging
import tempfile
import sqlite3
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from google.cloud import speech
from pydub import AudioSegment

# Configure logging with more detailed format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Changed from INFO to DEBUG for more detailed logs
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
logger.info("Loading environment variables from .env file")
load_dotenv()

# Get environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
logger.info(f"Loaded TELEGRAM_TOKEN: {TELEGRAM_TOKEN[:4]}...{TELEGRAM_TOKEN[-4:] if TELEGRAM_TOKEN else 'None'}")

# Constants
MAX_AUDIO_MINUTES = 50  # Maximum allowed audio processing time in minutes (global limit)
DB_PATH = os.getenv('DB_PATH', 'data/stats.db')  # Database file path, can be overridden by env var

# Create data directory if it doesn't exist
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Initialize database connection
def init_db():
    """Initialize the SQLite database for tracking audio processing stats."""
    logger.info(f"Initializing database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audio_stats (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        username TEXT,
        audio_length_sec REAL NOT NULL,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create global stats table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS global_stats (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        total_audio_sec REAL DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Insert initial global stats record if it doesn't exist
    cursor.execute('''
    INSERT OR IGNORE INTO global_stats (id, total_audio_sec, last_updated)
    VALUES (1, 0, CURRENT_TIMESTAMP)
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialization completed")

# Track audio processing in the database
def track_audio_processing(user_id, username, audio_length_sec):
    """Record audio processing stats in the database and update global counter."""
    logger.info(f"Tracking audio processing: {username} ({user_id}), {audio_length_sec:.2f} seconds")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Insert record into audio_stats
        cursor.execute(
            "INSERT INTO audio_stats (user_id, username, audio_length_sec) VALUES (?, ?, ?)",
            (user_id, username, audio_length_sec)
        )
        
        # Update global stats
        cursor.execute('''
        UPDATE global_stats 
        SET total_audio_sec = total_audio_sec + ?, 
            last_updated = CURRENT_TIMESTAMP
        WHERE id = 1
        ''', (audio_length_sec,))
        
        conn.commit()
        conn.close()
        logger.info(f"Successfully tracked audio processing for user {user_id}")
    except Exception as e:
        logger.error(f"Error tracking audio processing: {e}")

# Check if global audio limit has been exceeded
def check_global_audio_limit():
    """Check if the total audio processing time has exceeded the global limit."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get total audio time
        cursor.execute("SELECT total_audio_sec FROM global_stats WHERE id = 1")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            total_audio_sec = result[0]
            total_audio_min = total_audio_sec / 60
            logger.info(f"Global audio usage: {total_audio_min:.2f} minutes")
            return total_audio_min >= MAX_AUDIO_MINUTES, total_audio_min
        
        return False, 0
    except Exception as e:
        logger.error(f"Error checking global audio limit: {e}")
        # In case of error, allow processing to proceed
        return False, 0

# Get global usage stats
def get_global_stats():
    """Get total audio processing stats."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT total_audio_sec, last_updated FROM global_stats WHERE id = 1")
        result = cursor.fetchone()
        
        # Get top 5 users
        cursor.execute('''
        SELECT username, SUM(audio_length_sec) as total_sec
        FROM audio_stats
        GROUP BY username
        ORDER BY total_sec DESC
        LIMIT 5
        ''')
        top_users = cursor.fetchall()
        
        conn.close()
        
        if result:
            total_audio_sec = result[0]
            last_updated = result[1]
            return {
                'total_audio_min': total_audio_sec / 60,
                'last_updated': last_updated,
                'top_users': [(username, sec/60) for username, sec in top_users]
            }
        
        return {
            'total_audio_min': 0, 
            'last_updated': None,
            'top_users': []
        }
    except Exception as e:
        logger.error(f"Error getting global stats: {e}")
        return {
            'total_audio_min': 0, 
            'last_updated': None,
            'top_users': []
        }

# Get user-specific stats
def get_user_stats(user_id):
    """Get audio processing stats for a specific user."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get user's total audio time
        cursor.execute('''
        SELECT SUM(audio_length_sec), MAX(processed_at)
        FROM audio_stats
        WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            total_audio_sec = result[0]
            last_updated = result[1]
            return {
                'total_audio_min': total_audio_sec / 60,
                'last_updated': last_updated
            }
        
        return {'total_audio_min': 0, 'last_updated': None}
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {'total_audio_min': 0, 'last_updated': None}

# Debug environment
def log_sensitive_info(value):
    """Mask sensitive values for logging."""
    if not value or len(value) < 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"

# Log key environment variables and config
logger.info("Configuration summary:")
# Log the existence of .env file
env_path = os.path.join(os.getcwd(), '.env')
env_exists = os.path.exists(env_path)
logger.info(f".env file: {'Present' if env_exists else 'Not found'} at {env_path}")

# Log critical environment variables with masking
critical_vars = {
    "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
    "GOOGLE_APPLICATION_CREDENTIALS": os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
}

for key, value in critical_vars.items():
    if value:
        logger.info(f"  {key}: {log_sensitive_info(value) if 'TOKEN' in key or 'KEY' in key or 'SECRET' in key else value}")
    else:
        logger.error(f"  {key}: Missing")

if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN not found in environment variables.")
    raise ValueError("TELEGRAM_TOKEN not found in environment variables.")

# Initialize the database
init_db()

# Initialize Google Cloud Speech client
try:
    logger.info("Initializing Google Cloud Speech client")
    speech_client = speech.SpeechClient()
    logger.info("Google Cloud Speech client initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Google Cloud Speech client: {e}")
    raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Hi! I am a voice message transcription bot. '
        'Forward me voice messages, and I will transcribe them to text. '
        'I specialize in Serbian language transcription.'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        'Forward me a voice message and I will transcribe it to text. '
        'Currently optimized for Serbian language.\n\n'
        'Use /stats to see your usage statistics.\n'
        'Use /globalstats to see global usage statistics.'
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send user's audio processing statistics."""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    user_stats = get_user_stats(user_id)
    global_limit_reached, global_usage = check_global_audio_limit()
    
    message = f"📊 *Usage Statistics for {username}*\n\n"
    message += f"🎤 Your total audio processed: {user_stats['total_audio_min']:.2f} minutes\n"
    
    if user_stats['last_updated']:
        message += f"🕒 Your last activity: {user_stats['last_updated']}\n\n"
    
    message += f"🌐 Global usage: {global_usage:.2f}/{MAX_AUDIO_MINUTES} minutes"
    
    if global_limit_reached:
        message += "\n⚠️ Global limit reached. No more transcriptions available."
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def global_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send global audio processing statistics."""
    stats = get_global_stats()
    
    message = f"🌐 *Global Usage Statistics*\n\n"
    message += f"🎤 Total audio processed: {stats['total_audio_min']:.2f} minutes\n"
    message += f"⏳ Remaining quota: {max(0, MAX_AUDIO_MINUTES - stats['total_audio_min']):.2f} minutes\n"
    
    if stats['last_updated']:
        message += f"🕒 Last activity: {stats['last_updated']}\n\n"
    
    message += f"Maximum allowed audio processing is {MAX_AUDIO_MINUTES} minutes in total.\n\n"
    
    if stats['top_users']:
        message += "*Top users:*\n"
        for i, (username, minutes) in enumerate(stats['top_users'], 1):
            message += f"{i}. {username or 'Unknown'}: {minutes:.2f} minutes\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

def transcribe_audio(file_path):
    """Transcribe the given audio file using Google Speech-to-Text API."""
    try:
        # Convert the audio file to the correct format (WAV, mono, 16kHz, 16-bit)
        temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        logger.info(f"Converting audio file to proper format: {file_path} -> {temp_wav}")
        
        audio = AudioSegment.from_file(file_path)
        audio = audio.set_channels(1)  # Convert to mono
        audio = audio.set_frame_rate(16000)  # Convert to 16kHz
        audio = audio.set_sample_width(2)  # Convert to 16-bit (2 bytes per sample)
        
        logger.info(f"Audio properties after conversion: channels={audio.channels}, frame_rate={audio.frame_rate}, sample_width={audio.sample_width}")
        audio.export(temp_wav, format="wav")
        
        # Read the audio file
        with open(temp_wav, "rb") as audio_file:
            content = audio_file.read()
        
        # Configure the audio to be recognized
        audio_for_speech = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="sr-RS",  # Serbian language code
            model="default",
            enable_automatic_punctuation=True,
        )
        
        # Detect speech in the audio file
        logger.info("Sending audio to Google Speech-to-Text API")
        response = speech_client.recognize(config=config, audio=audio_for_speech)
        
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript
        
        # Clean up temporary files
        os.unlink(temp_wav)
        os.unlink(file_path)
        
        # Return audio length in seconds and the transcript
        return len(audio) / 1000, transcript  # Length in seconds
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        return 0, f"Transcription error: {str(e)}"

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages and transcribe them."""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    # Check if global limit has been exceeded
    limit_reached, current_usage = check_global_audio_limit()
    if limit_reached:
        await update.message.reply_text(
            f"⚠️ Sorry, the global audio processing limit has been reached "
            f"({MAX_AUDIO_MINUTES} minutes). No more transcriptions are available."
        )
        return
    
    # Reply to let the user know we're processing the voice message
    message = await update.message.reply_text("Processing your voice message...")
    
    try:
        # Get the voice message file
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        
        # Download the file to a temporary location
        temp_file = tempfile.NamedTemporaryFile(delete=False).name
        await voice_file.download_to_drive(temp_file)
        
        # Transcribe the voice message and get audio length in an executor
        audio_length_sec, transcript = await asyncio.to_thread(transcribe_audio, temp_file)
        
        # Track the audio processing
        track_audio_processing(user_id, username, audio_length_sec)
        
        # Check if this transcription put us over the limit
        limit_reached, current_usage = check_global_audio_limit()
        limit_message = ""
        if limit_reached:
            limit_message = f"\n\n⚠️ Global limit reached: {current_usage:.2f}/{MAX_AUDIO_MINUTES} minutes used."
        
        # Reply with the transcript
        if transcript:
            await message.edit_text(f"Transcript: {transcript}{limit_message}")
        else:
            await message.edit_text(f"Sorry, I couldn't transcribe that voice message.{limit_message}")
    except Exception as e:
        logger.error(f"Error handling voice message: {e}")
        await message.edit_text(f"Error: {str(e)}")

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token
    logger.info("Starting bot using non-asyncio entry point")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("globalstats", global_stats_command))
    
    # Add message handler for voice messages
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Use the blocking version which handles its own event loop
    logger.info("Running bot with run_polling()")
    app.run_polling(drop_pending_updates=True)
    logger.info("Bot stopped")

if __name__ == '__main__':
    main()