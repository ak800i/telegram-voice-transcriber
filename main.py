#!/usr/bin/env python
import os
import logging
import tempfile
import sqlite3
import datetime
from dotenv import load_dotenv
import assemblyai as aai
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from pydub import AudioSegment
import ffmpeg

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
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')

logger.info(f"Loaded TELEGRAM_TOKEN: {TELEGRAM_TOKEN[:4]}...{TELEGRAM_TOKEN[-4:] if TELEGRAM_TOKEN else 'None'}")
logger.info(f"Loaded ASSEMBLYAI_API_KEY: {ASSEMBLYAI_API_KEY[:4]}...{ASSEMBLYAI_API_KEY[-4:] if ASSEMBLYAI_API_KEY else 'None'}")

# Configure AssemblyAI
aai.settings.api_key = ASSEMBLYAI_API_KEY

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
logger.info("Environment variables:")
for key, value in os.environ.items():
    if 'TOKEN' in key or 'KEY' in key or 'SECRET' in key:
        # Mask sensitive values
        logger.info(f"  {key}: {value[:4]}...{value[-4:]}")
    else:
        logger.info(f"  {key}: {value}")

# Check if .env file exists and readable
env_path = os.path.join(os.getcwd(), '.env')
logger.info(f"Checking .env file at {env_path}")
if os.path.exists(env_path):
    logger.info(f".env file exists at {env_path}")
    try:
        with open(env_path, 'r') as f:
            env_content = f.read()
            # Log first few chars of each line to avoid exposing tokens
            logger.info("Contents of .env file (partially masked):")
            for line in env_content.splitlines():
                if line.strip() and not line.strip().startswith('#'):
                    key_val = line.split('=', 1)
                    if len(key_val) == 2:
                        key, val = key_val
                        if 'TOKEN' in key or 'KEY' in key or 'SECRET' in key:
                            logger.info(f"  {key}={val[:4]}...{val[-4:]}")
                        else:
                            logger.info(f"  {key}={val}")
    except Exception as e:
        logger.error(f"Error reading .env file: {e}")
else:
    logger.error(f".env file does not exist at {env_path}")

if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN not found in environment variables.")
    raise ValueError("TELEGRAM_TOKEN not found in environment variables.")

if not ASSEMBLYAI_API_KEY:
    logger.error("ASSEMBLYAI_API_KEY not found in environment variables.")
    raise ValueError("ASSEMBLYAI_API_KEY not found in environment variables.")

# Initialize the database
init_db()

# Initialize AssemblyAI transcriber with Serbian language configuration
transcriber = aai.Transcriber(
    config=aai.TranscriptionConfig(
        language_code="sr"  # Serbian language code
    )
)
logger.info("AssemblyAI transcriber initialized successfully")

def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    update.message.reply_text(
        'Hi! I am a voice message transcription bot. '
        'Forward me voice messages, and I will transcribe them to text. '
        'I specialize in Serbian language transcription.'
    )

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text(
        'Forward me a voice message and I will transcribe it to text. '
        'Currently optimized for Serbian language.\n\n'
        'Use /stats to see your usage statistics.\n'
        'Use /globalstats to see global usage statistics.'
    )

def stats_command(update: Update, context: CallbackContext) -> None:
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
    
    update.message.reply_text(message, parse_mode='Markdown')

def global_stats_command(update: Update, context: CallbackContext) -> None:
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
    
    update.message.reply_text(message, parse_mode='Markdown')

def transcribe_audio(file_path):
    """Transcribe the given audio file using AssemblyAI."""
    try:
        # Convert the audio file to the correct format (MP3)
        temp_mp3 = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
        logger.info(f"Converting audio file to proper format: {file_path} -> {temp_mp3}")
        
        audio = AudioSegment.from_file(file_path)
        audio_length_sec = len(audio) / 1000  # Get audio length in seconds
        
        # Export as MP3 for AssemblyAI
        audio.export(temp_mp3, format="mp3")
        
        # Send to AssemblyAI for transcription
        logger.info("Sending audio to AssemblyAI")
        transcript = transcriber.transcribe(temp_mp3)
        
        if transcript.status == "error":
            logger.error(f"Transcription error: {transcript.error}")
            return audio_length_sec, f"Transcription error: {transcript.error}"
        
        # Clean up temporary files
        os.unlink(temp_mp3)
        os.unlink(file_path)
        
        # Return audio length in seconds and the transcript
        return audio_length_sec, transcript.text
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        return 0, f"Transcription error: {str(e)}"

def handle_voice(update: Update, context: CallbackContext) -> None:
    """Handle voice messages and transcribe them."""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    # Check if global limit has been exceeded
    limit_reached, current_usage = check_global_audio_limit()
    if limit_reached:
        update.message.reply_text(
            f"⚠️ Sorry, the global audio processing limit has been reached "
            f"({MAX_AUDIO_MINUTES} minutes). No more transcriptions are available."
        )
        return
    
    # Reply to let the user know we're processing the voice message
    message = update.message.reply_text("Processing your voice message...")
    
    try:
        # Get the voice message file
        voice_file = context.bot.get_file(update.message.voice.file_id)
        
        # Download the file to a temporary location
        temp_file = tempfile.NamedTemporaryFile(delete=False).name
        voice_file.download(temp_file)
        
        # Transcribe the voice message and get audio length
        audio_length_sec, transcript = transcribe_audio(temp_file)
        
        # Track the audio processing
        track_audio_processing(user_id, username, audio_length_sec)
        
        # Check if this transcription put us over the limit
        limit_reached, current_usage = check_global_audio_limit()
        limit_message = ""
        if limit_reached:
            limit_message = f"\n\n⚠️ Global limit reached: {current_usage:.2f}/{MAX_AUDIO_MINUTES} minutes used."
        
        # Reply with the transcript
        if transcript:
            message.edit_text(f"Transcript: {transcript}{limit_message}")
        else:
            message.edit_text(f"Sorry, I couldn't transcribe that voice message.{limit_message}")
    except Exception as e:
        logger.error(f"Error handling voice message: {e}")
        message.edit_text(f"Error: {str(e)}")

def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token
    updater = Updater(TELEGRAM_TOKEN)
    
    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    
    # Add command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("stats", stats_command))
    dispatcher.add_handler(CommandHandler("globalstats", global_stats_command))
    
    # Add message handler for voice messages
    dispatcher.add_handler(MessageHandler(Filters.voice, handle_voice))
    
    # Start the Bot
    updater.start_polling()
    logger.info("Bot started")
    
    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__ == '__main__':
    main()