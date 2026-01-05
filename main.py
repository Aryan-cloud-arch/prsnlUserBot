"""
╔══════════════════════════════════════════════════════════════╗
║           ARYAN'S 24/7 AI USERBOT - @MaiHuAryan             ║
║                   Serious • Sarcastic • Hinglish             ║
║                                                              ║
║  Version: 2.0 (Production Ready)                            ║
║  Last Audit: Complete                                        ║
╚══════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════
#                         IMPORTS
# ═══════════════════════════════════════════════════════════════

import os
import sys
import asyncio
import random
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, List, Dict, Any

import pytz
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ChatAction, ParseMode
from pyrogram.errors import (
    FloodWait, 
    UserIsBlocked, 
    PeerIdInvalid,
    MessageNotModified,
    RPCError
)
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ═══════════════════════════════════════════════════════════════
#                         LOGGING SETUP
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#                         CONFIGURATION
# ═══════════════════════════════════════════════════════════════

load_dotenv()

def get_env(key: str, default: str = None, required: bool = False) -> Optional[str]:
    """Safely get environment variable"""
    value = os.getenv(key, default)
    if required and not value:
        logger.critical(f"❌ Missing required environment variable: {key}")
        sys.exit(1)
    return value

def get_env_int(key: str, default: int = 0, required: bool = False) -> int:
    """Safely get integer environment variable"""
    value = get_env(key, str(default), required)
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.error(f"❌ Invalid integer for {key}: {value}")
        return default

# Telegram Config
API_ID = get_env_int("API_ID", required=True)
API_HASH = get_env("API_HASH", required=True)
SESSION_STRING = get_env("SESSION_STRING", required=True)
OWNER_ID = get_env_int("OWNER_ID", default=0)

# MongoDB Config
MONGO_URI = get_env("MONGO_URI", required=True)

# Bot Identity
BOT_USERNAME = "MaiHuAryan"
BOT_NAME = "Aryan"
TIMEZONE = pytz.timezone("Asia/Kolkata")

# Gemini Config
GEMINI_MODEL = "gemini-1.5-flash"  # Updated from deprecated gemini-pro

# Safety Settings for Gemini
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# ═══════════════════════════════════════════════════════════════
#                      DATABASE SETUP
# ═══════════════════════════════════════════════════════════════

def connect_mongodb() -> MongoClient:
    """Connect to MongoDB with error handling"""
    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            retryWrites=True
        )
        # Test connection
        client.admin.command('ping')
        logger.info("✅ MongoDB connected successfully")
        return client
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.critical(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)

mongo_client = connect_mongodb()
db = mongo_client['aryan_userbot']

# Collections
messages_db = db['messages']
config_db = db['config']
vips_db = db['vips']
gemini_keys_db = db['gemini_keys']
stickers_db = db['stickers']
logs_db = db['logs']

# Create indexes for better performance
try:
    messages_db.create_index("user_id", unique=True)
    vips_db.create_index("user_id", unique=True)
    config_db.create_index("key", unique=True)
    logger.info("✅ Database indexes created")
except Exception as e:
    logger.warning(f"⚠️ Index creation warning: {e}")

# ═══════════════════════════════════════════════════════════════
#                      INITIALIZE CLIENT
# ═══════════════════════════════════════════════════════════════

app = Client(
    name="aryan_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

# ═══════════════════════════════════════════════════════════════
#                      GLOBAL VARIABLES
# ═══════════════════════════════════════════════════════════════

spam_tracker: Dict[int, List[Dict]] = defaultdict(list)
action_logs: List[str] = []
error_logs: List[str] = []

# ═══════════════════════════════════════════════════════════════
#                      HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_current_time() -> datetime:
    """Get current time in IST"""
    return datetime.now(TIMEZONE)

def get_config(key: str, default: Any = None) -> Any:
    """Get config value from database safely"""
    try:
        config = config_db.find_one({"key": key})
        if config and "value" in config:
            return config["value"]
        return default
    except Exception as e:
        logger.error(f"Config read error for {key}: {e}")
        return default

def set_config(key: str, value: Any) -> bool:
    """Set config value in database safely"""
    try:
        config_db.update_one(
            {"key": key},
            {"$set": {"key": key, "value": value}},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Config write error for {key}: {e}")
        return False

def log_action(action: str) -> None:
    """Log action for debugging"""
    global action_logs
    timestamp = get_current_time().strftime('%H:%M:%S')
    log_entry = f"[{timestamp}] {action}"
    action_logs.append(log_entry)
    if len(action_logs) > 50:
        action_logs = action_logs[-50:]
    logger.info(action)

def log_error(error: str) -> None:
    """Log error for debugging"""
    global error_logs
    timestamp = get_current_time().strftime('%H:%M:%S')
    log_entry = f"[{timestamp}] {error}"
    error_logs.append(log_entry)
    if len(error_logs) > 20:
        error_logs = error_logs[-20:]
    logger.error(error)

def is_bot_active() -> bool:
    """Check if bot is active"""
    return get_config("bot_active", False)

def get_owner_id() -> int:
    """Get owner ID from config or env"""
    return get_config("owner_id", OWNER_ID) or OWNER_ID

def is_owner(user_id: int) -> bool:
    """Check if user is owner"""
    owner = get_owner_id()
    return user_id == owner and owner != 0

def save_message(user_id: int, text: str, sender: str = "user") -> bool:
    """Save message to MongoDB safely"""
    try:
        messages_db.update_one(
            {"user_id": user_id},
            {
                "$push": {
                    "messages": {
                        "$each": [{
                            "text": text[:1000],  # Limit text length
                            "sender": sender,
                            "time": get_current_time().isoformat()
                        }],
                        "$slice": -100  # Keep only last 100 messages per user
                    }
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        log_error(f"Save message error: {e}")
        return False

def get_conversation_history(user_id: int, limit: int = 10) -> List[Dict]:
    """Get recent conversation with user safely"""
    try:
        user_data = messages_db.find_one({"user_id": user_id})
        if user_data and "messages" in user_data:
            return user_data["messages"][-limit:]
        return []
    except Exception as e:
        log_error(f"Get history error: {e}")
        return []

def get_all_gemini_keys() -> List[str]:
    """Get all Gemini API keys"""
    try:
        keys_doc = gemini_keys_db.find_one({"type": "keys"})
        if keys_doc and "keys" in keys_doc and keys_doc["keys"]:
            return keys_doc["keys"]
        
        # Initialize from env if not in DB
        keys = []
        for i in range(1, 15):  # Support up to 15 keys
            key = os.getenv(f"GEMINI_KEY_{i}")
            if key and key.strip():
                keys.append(key.strip())
        
        if keys:
            gemini_keys_db.update_one(
                {"type": "keys"},
                {"$set": {"keys": keys, "current_index": 0}},
                upsert=True
            )
            logger.info(f"✅ Loaded {len(keys)} Gemini keys from environment")
        
        return keys
    except Exception as e:
        log_error(f"Get Gemini keys error: {e}")
        return []

def get_next_gemini_key() -> Optional[str]:
    """Get next Gemini key with safe rotation"""
    try:
        keys = get_all_gemini_keys()
        if not keys:
            return None
        
        keys_doc = gemini_keys_db.find_one({"type": "keys"})
        current_index = 0
        
        if keys_doc and "current_index" in keys_doc:
            current_index = keys_doc["current_index"]
        
        # Ensure index is within bounds
        if current_index >= len(keys):
            current_index = 0
        
        key = keys[current_index]
        
        # Update index for next call
        next_index = (current_index + 1) % len(keys)
        gemini_keys_db.update_one(
            {"type": "keys"},
            {"$set": {"current_index": next_index}},
            upsert=True
        )
        
        return key
    except Exception as e:
        log_error(f"Key rotation error: {e}")
        return None

def get_vip_info(user_id: int) -> Optional[Dict]:
    """Get VIP information safely"""
    try:
        return vips_db.find_one({"user_id": user_id})
    except Exception as e:
        log_error(f"Get VIP error: {e}")
        return None

def is_vip(user_id: int) -> bool:
    """Check if user is VIP"""
    return get_vip_info(user_id) is not None

def get_log_group() -> Optional[int]:
    """Get log group chat ID"""
    return get_config("log_group_id")

async def send_log(text: str) -> bool:
    """Send log to log group safely"""
    log_group = get_log_group()
    if not log_group:
        return False
    
    try:
        await app.send_message(
            log_group, 
            f"📊 **LOG**\n\n{text}",
            parse_mode=ParseMode.MARKDOWN
        )
        return True
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await send_log(text)
    except Exception as e:
        logger.warning(f"Log send failed: {e}")
        return False

def count_words(text: str) -> int:
    """Count words in text safely"""
    if not text:
        return 0
    return len(text.split())

def is_spam(user_id: int, text: str) -> bool:
    """Detect spam (same message repeated)"""
    try:
        now = get_current_time()
        spam_tracker[user_id].append({"text": text, "time": now})
        
        # Keep only last 5 messages
        spam_tracker[user_id] = spam_tracker[user_id][-5:]
        
        # Check if last 3 messages are same within 1 minute
        recent = []
        for m in spam_tracker[user_id]:
            msg_time = m["time"]
            # Handle both datetime and string
            if isinstance(msg_time, str):
                try:
                    msg_time = datetime.fromisoformat(msg_time)
                except:
                    continue
            
            # Make timezone aware if not
            if msg_time.tzinfo is None:
                msg_time = TIMEZONE.localize(msg_time)
            
            time_diff = (now - msg_time).total_seconds()
            if time_diff < 60:
                recent.append(m)
        
        if len(recent) >= 3:
            texts = [m["text"] for m in recent]
            if len(set(texts)) == 1:  # All same
                return True
        
        return False
    except Exception as e:
        log_error(f"Spam check error: {e}")
        return False

def get_all_stickers() -> List[str]:
    """Get all sticker file IDs safely"""
    try:
        stickers_doc = stickers_db.find_one({"type": "stickers"})
        if stickers_doc and "file_ids" in stickers_doc:
            return stickers_doc["file_ids"]
        return []
    except Exception as e:
        log_error(f"Get stickers error: {e}")
        return []

def should_send_sticker() -> bool:
    """Determine if should send sticker"""
    try:
        chance = get_config("sticker_chance", 10)
        return random.randint(1, 100) <= chance
    except:
        return False

def get_delay_range() -> tuple:
    """Get reply delay range"""
    min_delay = get_config("delay_min", 3)
    max_delay = get_config("delay_max", 8)
    return (min_delay, max_delay)

def get_user_name(message: Message) -> str:
    """Safely get user's name"""
    try:
        if message.from_user:
            return message.from_user.first_name or f"User{message.from_user.id}"
        return "Unknown"
    except:
        return "Unknown"

def get_user_id_safe(message: Message) -> Optional[int]:
    """Safely get user ID"""
    try:
        if message.from_user:
            return message.from_user.id
        return None
    except:
        return None

# ═══════════════════════════════════════════════════════════════
#                      GEMINI AI HANDLER
# ═══════════════════════════════════════════════════════════════

ARYAN_PERSONALITY = """Tu Aryan hai (@MaiHuAryan). Telegram pe replies de raha hai.

PERSONALITY:
- Serious aur sarcastic ho
- Hinglish mein naturally baat kar (like: "kuch nhi yaar", "hn bhai bol", "acha thik hai")
- Emojis ALMOST ZERO use kar (very rarely, almost never)
- Short replies prefer kar, medium bhi chalega
- Tu mostly serious rehta hai, friendly sirf kuch logo ke saath

REPLY STYLE EXAMPLES:
- "kuch nhi, tu bta.."
- "hn?"
- "hn bhai bol bol"
- "acha"
- "hmm"
- "dekh lenge"
- "phir baat krte"
- "thik hai"
- "hehehehhe" (for funny stuff)
- "gunnite bhaii" (for goodnight)
- "ye toh phle se pta hai" (for compliments)
- "soja" (for bakwas/flirting/random nonsense)

TOPICS:
- Tu paisa kamane, skills sikhne, hustle ki baatein karta hai
- "skills sikh le", "kuch ukhaad" type vibes
- Motivate kar but sarcastically

SPECIAL RULES:
- If someone asks "tu bot hai?", "automated hai?" → Reply: "Kya farak padta hai, bol kaam kya hai"
- If someone asks personal info (number, address, photo) → Reply: "Ye sab Aryan se seedha puch lena"
- If someone asks about money/skills/earning → Reply: "Aryan se baat kar iske baare mein"
- If someone sends bakwas/flirts → Reply: "soja"
- If it's late night (after 1 AM) → Can add "bhai so ja" type replies

VIP HANDLING:
- If user is VIP with name "Soham" → Call "bhaiya", be extra friendly
- Other VIPs → Be friendly but normal

Current time: {current_time} IST
{vip_context}

CONVERSATION HISTORY:
{conversation_history}

User's new message: {user_message}

Reply as Aryan (short, natural Hinglish, NO quotes around reply):"""

async def get_ai_response(
    user_id: int, 
    message_text: str, 
    is_vip_user: bool = False, 
    vip_name: Optional[str] = None
) -> str:
    """Get AI response from Gemini with proper error handling"""
    
    fallback_response = "Aryan off hai, aaega toh I will let you know"
    
    try:
        # Get conversation history
        history = get_conversation_history(user_id, limit=10)
        
        # Build conversation context
        conversation_history = ""
        if history:
            for msg in history[-5:]:
                sender = "User" if msg.get("sender") == "user" else "Aryan"
                text = msg.get("text", "")[:200]  # Limit context length
                conversation_history += f"{sender}: {text}\n"
        else:
            conversation_history = "(No previous conversation)"
        
        # VIP context
        vip_context = ""
        if is_vip_user and vip_name:
            if vip_name.lower() == "soham":
                vip_context = f"IMPORTANT: This is {vip_name} (VIP). Call him 'bhaiya', be extra friendly and warm."
            else:
                vip_context = f"IMPORTANT: This is {vip_name} (VIP). Be friendly with them."
        
        # Current time
        current_time = get_current_time().strftime("%I:%M %p, %d %b %Y")
        
        # Build final prompt
        prompt = ARYAN_PERSONALITY.format(
            current_time=current_time,
            vip_context=vip_context,
            conversation_history=conversation_history,
            user_message=message_text
        )
        
        # Try with key rotation
        keys = get_all_gemini_keys()
        max_attempts = len(keys) if keys else 1
        
        for attempt in range(max_attempts):
            try:
                api_key = get_next_gemini_key()
                if not api_key:
                    log_error("No Gemini API keys available")
                    return fallback_response
                
                genai.configure(api_key=api_key)
                
                model = genai.GenerativeModel(
                    model_name=GEMINI_MODEL,
                    safety_settings=SAFETY_SETTINGS
                )
                
                # Run in thread to prevent blocking
                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt
                )
                
                # Check for valid response
                if not response or not response.text:
                    log_error(f"Empty Gemini response on attempt {attempt + 1}")
                    continue
                
                reply = response.text.strip()
                
                # Clean up reply
                reply = reply.replace("Aryan:", "").strip()
                reply = reply.strip('"').strip("'").strip()
                
                # Remove any asterisks (markdown bold)
                reply = reply.replace("*", "")
                
                # Validate reply
                if not reply or len(reply) < 1:
                    continue
                
                # Limit reply length
                if len(reply) > 500:
                    reply = reply[:500] + "..."
                
                log_action(f"AI replied to {user_id}: {reply[:50]}...")
                return reply
                
            except Exception as e:
                error_str = str(e).lower()
                if "quota" in error_str or "429" in error_str or "resource" in error_str:
                    log_action(f"Key {attempt + 1} quota exceeded, rotating...")
                    continue
                elif "block" in error_str or "safety" in error_str:
                    log_error(f"Content blocked by safety filter")
                    return "hmm kya bol rha hai"
                else:
                    log_error(f"Gemini error: {e}")
                    continue
        
        # All keys failed
        log_error("All Gemini keys exhausted")
        return fallback_response
        
    except Exception as e:
        log_error(f"AI response error: {e}")
        return fallback_response

# ═══════════════════════════════════════════════════════════════
#                      MESSAGE HANDLERS
# ═══════════════════════════════════════════════════════════════

@app.on_message(filters.private & ~filters.me & ~filters.bot & ~filters.channel)
async def handle_private_message(client: Client, message: Message):
    """Handle private messages"""
    
    # Check if bot is active
    if not is_bot_active():
        return
    
    # Safely get user info
    user_id = get_user_id_safe(message)
    if not user_id:
        return
    
    user_name = get_user_name(message)
    
    try:
        # Ignore stickers completely
        if message.sticker:
            log_action(f"Ignored sticker from {user_name}")
            return
        
        # Handle media (photo, video, document, voice, etc.)
        if not message.text:
            save_message(user_id, "[MEDIA]", "user")
            
            # Show playing animation
            await show_playing_animation(client, message.chat.id)
            
            # Determine response based on media type
            if message.voice or message.audio:
                reply = "Aryan ko aane do, dekh lega"
            elif message.video_note:
                reply = "Aryan ko aane do, dekh lega"
            else:
                reply = "mujhe kuch dikhai nhi de rha abhi"
            
            await safe_reply(message, reply)
            save_message(user_id, reply, "bot")
            await send_log(f"📸 Media from {user_name} ({user_id})\n↳ {reply}")
            return
        
        text = message.text.strip()
        if not text:
            return
        
        # Save incoming message
        save_message(user_id, text, "user")
        
        # Check spam
        if is_spam(user_id, text):
            await show_playing_animation(client, message.chat.id, short=True)
            reply = "Ek baar bol, spam mat kar"
            await safe_reply(message, reply)
            save_message(user_id, reply, "bot")
            log_action(f"Spam detected from {user_name}")
            return
        
        # Check long message (>200 words)
        if count_words(text) > 200:
            await show_playing_animation(client, message.chat.id, short=True)
            reply = "Bhai itna lamba, summary bol"
            await safe_reply(message, reply)
            save_message(user_id, reply, "bot")
            return
        
        # Check if first message from this user
        first_msg_enabled = get_config("first_msg_enabled", True)
        user_history = get_conversation_history(user_id)
        
        if first_msg_enabled and len(user_history) <= 1:
            await show_playing_animation(client, message.chat.id)
            reply = "⚠️ This is automated. Real reply baad mein.\n\nHn bhai bol, Aryan baad mein dekh lega"
            await safe_reply(message, reply)
            save_message(user_id, reply, "bot")
            await send_log(f"🆕 First message from {user_name} ({user_id})\n↳ {text[:100]}")
            return
        
        # Check VIP status
        vip_info = get_vip_info(user_id)
        is_vip_user = vip_info is not None
        vip_name = vip_info.get("name") if vip_info else None
        
        # Get AI response
        ai_reply = await get_ai_response(user_id, text, is_vip_user, vip_name)
        
        # Show playing animation with smart delay
        await show_playing_animation(client, message.chat.id, reply_length=len(ai_reply))
        
        # Maybe send sticker (10% chance, before reply)
        if should_send_sticker():
            stickers = get_all_stickers()
            if stickers:
                try:
                    sticker_id = random.choice(stickers)
                    await message.reply_sticker(sticker_id)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    log_error(f"Sticker send error: {e}")
        
        # Send reply
        await safe_reply(message, ai_reply)
        save_message(user_id, ai_reply, "bot")
        
        # Log
        log_action(f"Replied to {user_name}: {ai_reply[:50]}...")
        await send_log(f"💬 **{user_name}** ({user_id})\n\n📩 {text[:100]}\n📤 {ai_reply[:100]}")
        
    except FloodWait as e:
        log_error(f"FloodWait: {e.value} seconds")
        await asyncio.sleep(e.value)
    except Exception as e:
        log_error(f"Message handler error: {e}")

@app.on_message(filters.group & ~filters.me & ~filters.bot)
async def handle_group_message(client: Client, message: Message):
    """Handle group messages (only when mentioned)"""
    
    if not is_bot_active():
        return
    
    # Check if bot is mentioned
    if not message.text:
        return
    
    if f"@{BOT_USERNAME}" not in message.text:
        return
    
    user_id = get_user_id_safe(message)
    if not user_id:
        return
    
    user_name = get_user_name(message)
    
    try:
        text = message.text.replace(f"@{BOT_USERNAME}", "").strip()
        
        if not text:
            text = "mentioned you"
        
        save_message(user_id, f"[GROUP] {text}", "user")
        
        # Get AI response
        vip_info = get_vip_info(user_id)
        ai_reply = await get_ai_response(
            user_id, 
            text, 
            vip_info is not None, 
            vip_info.get("name") if vip_info else None
        )
        
        # Add warning footer
        full_reply = f"{ai_reply}\n\n_⚠️ This is automated_"
        
        # Show animation
        await show_playing_animation(client, message.chat.id)
        
        # Reply
        await safe_reply(message, full_reply, parse_mode=ParseMode.MARKDOWN)
        save_message(user_id, ai_reply, "bot")
        
        log_action(f"Group reply to {user_name} in {message.chat.title}")
        
    except Exception as e:
        log_error(f"Group handler error: {e}")

async def show_playing_animation(
    client: Client, 
    chat_id: int, 
    short: bool = False,
    reply_length: int = 0
) -> None:
    """Show playing/typing animation"""
    try:
        # Try PLAYING action first (shows game controller)
        # If not available, fall back to CHOOSE_STICKER (shows searching animation)
        try:
            await client.send_chat_action(chat_id, ChatAction.PLAYING)
        except:
            await client.send_chat_action(chat_id, ChatAction.CHOOSE_STICKER)
        
        # Calculate delay based on context
        if short:
            delay = random.uniform(1.5, 3)
        elif reply_length > 100:
            delay = random.uniform(5, 8)
        elif reply_length > 50:
            delay = random.uniform(3, 6)
        else:
            min_d, max_d = get_delay_range()
            delay = random.uniform(min_d, max_d)
        
        await asyncio.sleep(delay)
        
    except Exception as e:
        logger.warning(f"Chat action error: {e}")
        await asyncio.sleep(2)

async def safe_reply(
    message: Message, 
    text: str, 
    parse_mode: ParseMode = None
) -> bool:
    """Safely reply to message with error handling"""
    try:
        await message.reply(text, parse_mode=parse_mode)
        return True
    except UserIsBlocked:
        log_error(f"User {message.from_user.id} blocked us")
        return False
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await safe_reply(message, text, parse_mode)
    except Exception as e:
        log_error(f"Reply error: {e}")
        return False

# ═══════════════════════════════════════════════════════════════
#                      OWNER COMMANDS
# ═══════════════════════════════════════════════════════════════

@app.on_message(filters.command("setowner") & filters.me)
async def set_owner_command(client: Client, message: Message):
    """Set owner ID (first time only)"""
    try:
        current_owner = get_owner_id()
        if current_owner != 0 and current_owner != message.from_user.id:
            await message.edit("❌ Owner already set by someone else!")
            return
        
        set_config("owner_id", message.from_user.id)
        await message.edit(f"✅ Owner set to: `{message.from_user.id}`")
        log_action("Owner ID set")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"setowner error: {e}")

@app.on_message(filters.command("boton") & filters.me)
async def bot_on_command(client: Client, message: Message):
    """Activate bot"""
    try:
        set_config("bot_active", True)
        await message.edit("🤖 **Bot Activated**\n\nNow replying to messages...")
        log_action("Bot activated")
        await send_log("🟢 Bot activated by owner")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"boton error: {e}")

@app.on_message(filters.command("botoff") & filters.me)
async def bot_off_command(client: Client, message: Message):
    """Deactivate bot with summary"""
    try:
        set_config("bot_active", False)
        
        # Generate summary
        summary_data = {}
        cutoff_time = get_current_time() - timedelta(hours=24)
        
        try:
            for user_data in messages_db.find():
                user_id = user_data.get("user_id")
                if not user_id:
                    continue
                
                messages = user_data.get("messages", [])
                recent_count = 0
                
                for msg in messages:
                    if msg.get("sender") != "user":
                        continue
                    
                    try:
                        msg_time_str = msg.get("time", "")
                        if not msg_time_str:
                            continue
                        
                        # Parse time safely
                        msg_time = datetime.fromisoformat(msg_time_str.replace('Z', '+00:00'))
                        
                        # Make timezone aware if needed
                        if msg_time.tzinfo is None:
                            msg_time = TIMEZONE.localize(msg_time)
                        
                        if msg_time > cutoff_time:
                            recent_count += 1
                    except:
                        continue
                
                if recent_count > 0:
                    summary_data[user_id] = recent_count
                    
        except Exception as e:
            log_error(f"Summary generation error: {e}")
        
        # Build summary message
        summary_text = "🤖 **Bot Deactivated**\n\n"
        
        if summary_data:
            summary_text += "📬 **Summary (last 24h):**\n"
            summary_text += "━━━━━━━━━━━━━━━━━━\n"
            
            total_msgs = 0
            sorted_users = sorted(summary_data.items(), key=lambda x: x[1], reverse=True)[:10]
            
            for user_id, count in sorted_users:
                try:
                    user = await client.get_users(user_id)
                    name = user.first_name or f"User{user_id}"
                    vip_info = get_vip_info(user_id)
                    if vip_info:
                        name = f"👑 {vip_info.get('name', name)}"
                except:
                    name = f"User {user_id}"
                
                summary_text += f"👤 {name} - {count} msgs\n"
                total_msgs += count
            
            summary_text += "━━━━━━━━━━━━━━━━━━\n"
            summary_text += f"**Total:** {total_msgs} messages from {len(summary_data)} people"
        else:
            summary_text += "📭 No messages received recently."
        
        await message.edit(summary_text)
        log_action("Bot deactivated")
        await send_log("🔴 Bot deactivated by owner")
        
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"botoff error: {e}")
        await message.edit("🤖 **Bot Deactivated**\n\n(Summary unavailable)")

@app.on_message(filters.command("status") & filters.me)
async def status_command(client: Client, message: Message):
    """Check bot status"""
    try:
        active = is_bot_active()
        status = "🟢 **ACTIVE**" if active else "🔴 **INACTIVE**"
        
        # Get stats
        total_users = messages_db.count_documents({})
        total_vips = vips_db.count_documents({})
        total_keys = len(get_all_gemini_keys())
        total_stickers = len(get_all_stickers())
        min_d, max_d = get_delay_range()
        
        status_text = f"""
📊 **Bot Status**

**State:** {status}

**Stats:**
├ Users: {total_users}
├ VIPs: {total_vips}
├ Gemini Keys: {total_keys}
├ Stickers: {total_stickers}
├ Delay: {min_d}-{max_d}s
└ Sticker Chance: {get_config("sticker_chance", 10)}%

**Features:**
├ First Msg: {"✅" if get_config("first_msg_enabled", True) else "❌"}
└ Log Group: {"✅" if get_log_group() else "❌"}

**System:**
├ Uptime: Running
└ Errors: {len(error_logs)}
"""
        await message.edit(status_text)
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"status error: {e}")

@app.on_message(filters.command("ping") & filters.me)
async def ping_command(client: Client, message: Message):
    """Check if bot is alive"""
    try:
        start = datetime.now()
        await message.edit("🏓 Pinging...")
        end = datetime.now()
        ping_ms = (end - start).microseconds / 1000
        await message.edit(f"🏓 **Pong!**\n\nLatency: `{ping_ms:.2f}ms`")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"ping error: {e}")

# ═══════════════════════════════════════════════════════════════
#                      VIP MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@app.on_message(filters.command("addvip") & filters.me)
async def add_vip_command(client: Client, message: Message):
    """Add VIP user"""
    try:
        user_id = None
        
        # Check if reply
        if message.reply_to_message and message.reply_to_message.from_user:
            user_id = message.reply_to_message.from_user.id
        elif len(message.command) > 1:
            try:
                user_id = int(message.command[1])
            except ValueError:
                await message.edit("❌ Invalid user ID")
                return
        else:
            await message.edit("❌ Reply to a message or provide user ID\n\n**Usage:** `/addvip` or `/addvip 123456789`")
            return
        
        # Add to VIPs
        vips_db.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "name": f"User{user_id}"}},
            upsert=True
        )
        
        await message.edit(f"✅ Added VIP: `{user_id}`\n\nSet name: `/vipname {user_id} Name`")
        log_action(f"VIP added: {user_id}")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"addvip error: {e}")

@app.on_message(filters.command("removevip") & filters.me)
async def remove_vip_command(client: Client, message: Message):
    """Remove VIP user"""
    try:
        user_id = None
        
        if message.reply_to_message and message.reply_to_message.from_user:
            user_id = message.reply_to_message.from_user.id
        elif len(message.command) > 1:
            try:
                user_id = int(message.command[1])
            except ValueError:
                await message.edit("❌ Invalid user ID")
                return
        else:
            await message.edit("❌ Reply to a message or provide user ID")
            return
        
        result = vips_db.delete_one({"user_id": user_id})
        
        if result.deleted_count > 0:
            await message.edit(f"✅ Removed VIP: `{user_id}`")
            log_action(f"VIP removed: {user_id}")
        else:
            await message.edit("❌ User not in VIP list")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"removevip error: {e}")

@app.on_message(filters.command("listvip") & filters.me)
async def list_vip_command(client: Client, message: Message):
    """List all VIPs"""
    try:
        vips = list(vips_db.find())
        
        if not vips:
            await message.edit("👑 No VIPs added yet\n\nUse `/addvip` to add")
            return
        
        vip_list = "👑 **VIP List**\n\n"
        for i, vip in enumerate(vips, 1):
            vip_list += f"{i}. **{vip.get('name', 'Unknown')}**\n   └ ID: `{vip['user_id']}`\n"
        
        await message.edit(vip_list)
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"listvip error: {e}")

@app.on_message(filters.command("vipname") & filters.me)
async def vip_name_command(client: Client, message: Message):
    """Set VIP custom name"""
    try:
        if len(message.command) < 3:
            await message.edit("❌ **Usage:** `/vipname 123456789 Soham`")
            return
        
        try:
            user_id = int(message.command[1])
        except ValueError:
            await message.edit("❌ Invalid user ID")
            return
        
        name = " ".join(message.command[2:])
        
        vips_db.update_one(
            {"user_id": user_id},
            {"$set": {"name": name}},
            upsert=True
        )
        
        await message.edit(f"✅ VIP name set: **{name}** (`{user_id}`)")
        log_action(f"VIP name set: {name}")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"vipname error: {e}")

# ═══════════════════════════════════════════════════════════════
#                      GEMINI KEY MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@app.on_message(filters.command("addkey") & filters.me)
async def add_key_command(client: Client, message: Message):
    """Add Gemini API key"""
    try:
        if len(message.command) < 2:
            await message.edit("❌ **Usage:** `/addkey AIzaSyXXXXXX...`")
            return
        
        key = message.command[1].strip()
        
        if not key.startswith("AIza"):
            await message.edit("❌ Invalid Gemini key format (should start with AIza)")
            return
        
        # Get current keys
        keys = get_all_gemini_keys()
        
        if key in keys:
            await message.edit("❌ Key already exists!")
            return
        
        keys.append(key)
        
        # Update DB
        gemini_keys_db.update_one(
            {"type": "keys"},
            {"$set": {"keys": keys}},
            upsert=True
        )
        
        # Delete the command message (contains key)
        await message.delete()
        await client.send_message(
            message.chat.id,
            f"✅ Gemini key added!\n\n**Total keys:** {len(keys)}"
        )
        log_action("Gemini key added")
    except Exception as e:
        log_error(f"addkey error: {e}")

@app.on_message(filters.command("removekey") & filters.me)
async def remove_key_command(client: Client, message: Message):
    """Remove Gemini key by index"""
    try:
        if len(message.command) < 2:
            await message.edit("❌ **Usage:** `/removekey 3`")
            return
        
        try:
            index = int(message.command[1]) - 1
        except ValueError:
            await message.edit("❌ Invalid number")
            return
        
        keys = get_all_gemini_keys()
        
        if 0 <= index < len(keys):
            keys.pop(index)
            gemini_keys_db.update_one(
                {"type": "keys"},
                {"$set": {"keys": keys, "current_index": 0}}
            )
            await message.edit(f"✅ Key #{index + 1} removed\n\n**Remaining:** {len(keys)}")
            log_action(f"Gemini key removed: #{index + 1}")
        else:
            await message.edit(f"❌ Invalid key number (1-{len(keys)})")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"removekey error: {e}")

@app.on_message(filters.command("listkeys") & filters.me)
async def list_keys_command(client: Client, message: Message):
    """List all Gemini keys (masked)"""
    try:
        keys = get_all_gemini_keys()
        
        if not keys:
            await message.edit("🔑 No Gemini keys configured\n\nUse `/addkey` to add")
            return
        
        keys_doc = gemini_keys_db.find_one({"type": "keys"})
        current_index = keys_doc.get("current_index", 0) if keys_doc else 0
        
        key_list = "🔑 **Gemini Keys**\n\n"
        for i, key in enumerate(keys):
            masked = key[:8] + "..." + key[-4:]
            current = " 👈 (current)" if i == current_index else ""
            key_list += f"{i + 1}. `{masked}`{current}\n"
        
        await message.edit(key_list)
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"listkeys error: {e}")

@app.on_message(filters.command("testkeys") & filters.me)
async def test_keys_command(client: Client, message: Message):
    """Test all Gemini keys"""
    try:
        keys = get_all_gemini_keys()
        
        if not keys:
            await message.edit("❌ No keys to test")
            return
        
        await message.edit("🔄 Testing keys...")
        
        results = ""
        for i, key in enumerate(keys):
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(GEMINI_MODEL)
                response = await asyncio.to_thread(
                    model.generate_content, 
                    "Say 'OK' only"
                )
                if response and response.text:
                    results += f"{i + 1}. ✅ Working\n"
                else:
                    results += f"{i + 1}. ⚠️ Empty response\n"
            except Exception as e:
                error = str(e)[:25]
                results += f"{i + 1}. ❌ {error}...\n"
        
        await message.edit(f"🔑 **Key Test Results**\n\n{results}")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"testkeys error: {e}")

# ═══════════════════════════════════════════════════════════════
#                      STICKER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@app.on_message(filters.command("addsticker") & filters.me)
async def add_sticker_command(client: Client, message: Message):
    """Add sticker to rotation"""
    try:
        if not message.reply_to_message or not message.reply_to_message.sticker:
            await message.edit("❌ Reply to a sticker!")
            return
        
        file_id = message.reply_to_message.sticker.file_id
        
        stickers_db.update_one(
            {"type": "stickers"},
            {"$addToSet": {"file_ids": file_id}},
            upsert=True
        )
        
        total = len(get_all_stickers())
        await message.edit(f"✅ Sticker added!\n\n**Total stickers:** {total}")
        log_action("Sticker added")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"addsticker error: {e}")

@app.on_message(filters.command("removesticker") & filters.me)
async def remove_sticker_command(client: Client, message: Message):
    """Remove sticker from rotation"""
    try:
        if not message.reply_to_message or not message.reply_to_message.sticker:
            await message.edit("❌ Reply to a sticker!")
            return
        
        file_id = message.reply_to_message.sticker.file_id
        
        stickers_db.update_one(
            {"type": "stickers"},
            {"$pull": {"file_ids": file_id}}
        )
        
        total = len(get_all_stickers())
        await message.edit(f"✅ Sticker removed!\n\n**Remaining:** {total}")
        log_action("Sticker removed")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"removesticker error: {e}")

@app.on_message(filters.command("liststickers") & filters.me)
async def list_stickers_command(client: Client, message: Message):
    """List all stickers"""
    try:
        stickers = get_all_stickers()
        
        if not stickers:
            await message.edit("📎 No stickers added\n\nReply to a sticker with `/addsticker`")
            return
        
        await message.edit(f"📎 **Total Stickers:** {len(stickers)}\n\nSending preview...")
        
        # Show max 3 stickers as preview
        for sticker_id in stickers[:3]:
            try:
                await client.send_sticker(message.chat.id, sticker_id)
                await asyncio.sleep(0.3)
            except:
                pass
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"liststickers error: {e}")

@app.on_message(filters.command("stickerchance") & filters.me)
async def sticker_chance_command(client: Client, message: Message):
    """Set sticker send chance"""
    try:
        if len(message.command) < 2:
            current = get_config("sticker_chance", 10)
            await message.edit(f"🎲 Sticker chance: **{current}%**\n\n**Usage:** `/stickerchance 15`")
            return
        
        try:
            chance = int(message.command[1])
        except ValueError:
            await message.edit("❌ Invalid number")
            return
        
        if 0 <= chance <= 100:
            set_config("sticker_chance", chance)
            await message.edit(f"✅ Sticker chance set to **{chance}%**")
        else:
            await message.edit("❌ Value must be 0-100")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"stickerchance error: {e}")

# ═══════════════════════════════════════════════════════════════
#                      LOG GROUP MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@app.on_message(filters.command("setlog") & filters.me)
async def set_log_command(client: Client, message: Message):
    """Set log group"""
    try:
        if len(message.command) < 2:
            await message.edit("❌ **Usage:** `/setlog -1001234567890`")
            return
        
        try:
            chat_id = int(message.command[1])
        except ValueError:
            await message.edit("❌ Invalid chat ID")
            return
        
        set_config("log_group_id", chat_id)
        await message.edit(f"✅ Log group set to: `{chat_id}`")
        await send_log("🎉 Log group configured successfully!")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"setlog error: {e}")

@app.on_message(filters.command("testlog") & filters.me)
async def test_log_command(client: Client, message: Message):
    """Test log group"""
    try:
        log_group = get_log_group()
        if not log_group:
            await message.edit("❌ Log group not set!\n\nUse `/setlog -100xxxxx`")
            return
        
        success = await send_log("✅ Log test successful!")
        if success:
            await message.edit("✅ Log test sent!")
        else:
            await message.edit("❌ Failed to send log")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"testlog error: {e}")

@app.on_message(filters.command("disablelog") & filters.me)
async def disable_log_command(client: Client, message: Message):
    """Disable logging"""
    try:
        set_config("log_group_id", None)
        await message.edit("✅ Logging disabled")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"disablelog error: {e}")

# ═══════════════════════════════════════════════════════════════
#                      MEMORY MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@app.on_message(filters.command("clearmemory") & filters.me)
async def clear_memory_command(client: Client, message: Message):
    """Clear user's conversation history"""
    try:
        user_id = None
        
        if message.reply_to_message and message.reply_to_message.from_user:
            user_id = message.reply_to_message.from_user.id
        elif len(message.command) > 1:
            try:
                user_id = int(message.command[1])
            except ValueError:
                await message.edit("❌ Invalid user ID")
                return
        else:
            await message.edit("❌ Reply to a message or provide user ID")
            return
        
        result = messages_db.delete_one({"user_id": user_id})
        
        if result.deleted_count > 0:
            await message.edit(f"✅ Memory cleared for: `{user_id}`")
            log_action(f"Memory cleared: {user_id}")
        else:
            await message.edit(f"ℹ️ No memory found for: `{user_id}`")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"clearmemory error: {e}")

@app.on_message(filters.command("clearall") & filters.me)
async def clear_all_command(client: Client, message: Message):
    """Clear all conversation history (requires confirmation)"""
    try:
        total = messages_db.count_documents({})
        await message.edit(f"⚠️ This will delete **{total}** conversations!\n\nSend `/confirmclear` to proceed")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"clearall error: {e}")

@app.on_message(filters.command("confirmclear") & filters.me)
async def confirm_clear_command(client: Client, message: Message):
    """Confirm clear all"""
    try:
        count = messages_db.delete_many({}).deleted_count
        await message.edit(f"✅ Cleared **{count}** conversations")
        log_action("All memory cleared")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"confirmclear error: {e}")

@app.on_message(filters.command("memory") & filters.me)
async def memory_command(client: Client, message: Message):
    """Check user's message count"""
    try:
        user_id = None
        
        if message.reply_to_message and message.reply_to_message.from_user:
            user_id = message.reply_to_message.from_user.id
        elif len(message.command) > 1:
            try:
                user_id = int(message.command[1])
            except ValueError:
                await message.edit("❌ Invalid user ID")
                return
        else:
            await message.edit("❌ Reply to a message or provide user ID")
            return
        
        user_data = messages_db.find_one({"user_id": user_id})
        if user_data and "messages" in user_data:
            msg_count = len(user_data["messages"])
            await message.edit(f"💾 User `{user_id}`\n\n**Messages stored:** {msg_count}")
        else:
            await message.edit(f"ℹ️ No conversation history for `{user_id}`")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"memory error: {e}")

# ═══════════════════════════════════════════════════════════════
#                      SETTINGS COMMANDS
# ═══════════════════════════════════════════════════════════════

@app.on_message(filters.command("firstmsg") & filters.me)
async def first_msg_command(client: Client, message: Message):
    """Toggle first message greeting"""
    try:
        if len(message.command) < 2:
            current = get_config("first_msg_enabled", True)
            status = "ON ✅" if current else "OFF ❌"
            await message.edit(f"👋 First message greeting: **{status}**\n\n**Usage:** `/firstmsg on` or `/firstmsg off`")
            return
        
        toggle = message.command[1].lower()
        if toggle in ["on", "true", "1", "yes"]:
            set_config("first_msg_enabled", True)
            await message.edit("✅ First message greeting **enabled**")
        elif toggle in ["off", "false", "0", "no"]:
            set_config("first_msg_enabled", False)
            await message.edit("✅ First message greeting **disabled**")
        else:
            await message.edit("❌ Use `on` or `off`")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"firstmsg error: {e}")

@app.on_message(filters.command("delay") & filters.me)
async def delay_command(client: Client, message: Message):
    """Set reply delay range"""
    try:
        if len(message.command) < 2:
            min_d, max_d = get_delay_range()
            await message.edit(f"⏱️ Current delay: **{min_d}-{max_d}** seconds\n\n**Usage:** `/delay 3-8`")
            return
        
        try:
            delay_str = message.command[1]
            if "-" in delay_str:
                min_d, max_d = map(int, delay_str.split("-"))
            else:
                min_d = max_d = int(delay_str)
            
            if min_d < 1:
                min_d = 1
            if max_d > 30:
                max_d = 30
            if min_d > max_d:
                min_d, max_d = max_d, min_d
            
            set_config("delay_min", min_d)
            set_config("delay_max", max_d)
            await message.edit(f"✅ Delay set to **{min_d}-{max_d}** seconds")
        except:
            await message.edit("❌ Invalid format. Use: `/delay 3-8`")
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"delay error: {e}")

@app.on_message(filters.command("logs") & filters.me)
async def logs_command(client: Client, message: Message):
    """Show recent action logs"""
    try:
        if not action_logs:
            await message.edit("📋 No recent logs")
            return
        
        log_text = "📋 **Recent Logs** (last 10)\n\n"
        log_text += "```\n"
        log_text += "\n".join(action_logs[-10:])
        log_text += "\n```"
        
        await message.edit(log_text)
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"logs error: {e}")

@app.on_message(filters.command("error") & filters.me)
async def error_command(client: Client, message: Message):
    """Show recent errors"""
    try:
        if not error_logs:
            await message.edit("✅ No recent errors!")
            return
        
        error_text = "❌ **Recent Errors** (last 10)\n\n"
        error_text += "```\n"
        error_text += "\n".join(error_logs[-10:])
        error_text += "\n```"
        
        await message.edit(error_text)
    except MessageNotModified:
        pass
    except Exception as e:
        pass

@app.on_message(filters.command("restart") & filters.me)
async def restart_command(client: Client, message: Message):
    """Restart bot"""
    try:
        await message.edit("🔄 Restarting bot...")
        log_action("Bot restart initiated")
        await send_log("🔄 Bot restarting...")
        
        # Proper restart using os.execv
        os.execv(sys.executable, ['python'] + sys.argv)
    except Exception as e:
        log_error(f"restart error: {e}")
        await message.edit(f"❌ Restart failed: {e}")

@app.on_message(filters.command("help") & filters.me)
async def help_command(client: Client, message: Message):
    """Show help"""
    try:
        help_text = """
🤖 **Aryan's Userbot - Commands**

**🎛️ Basic:**
├ `/boton` - Activate bot
├ `/botoff` - Deactivate + summary
├ `/status` - Check status
└ `/ping` - Check latency

**👑 VIP:**
├ `/addvip` - Add VIP (reply/ID)
├ `/removevip` - Remove VIP
├ `/listvip` - List all VIPs
└ `/vipname ID Name` - Set name

**🔑 Gemini:**
├ `/addkey KEY` - Add API key
├ `/removekey #` - Remove key
├ `/listkeys` - Show all keys
└ `/testkeys` - Test all keys

**📎 Stickers:**
├ `/addsticker` - Add (reply)
├ `/removesticker` - Remove
├ `/liststickers` - List all
└ `/stickerchance %` - Set chance

**📊 Logs:**
├ `/setlog ID` - Set log group
├ `/testlog` - Test logging
└ `/disablelog` - Disable

**💾 Memory:**
├ `/clearmemory` - Clear user
├ `/clearall` - Clear all
└ `/memory` - Check count

**⚙️ Settings:**
├ `/firstmsg on/off` - Greeting
├ `/delay 3-8` - Reply delay
├ `/logs` - Action logs
├ `/error` - Error logs
├ `/restart` - Restart bot
└ `/help` - This message
"""
        await message.edit(help_text)
    except MessageNotModified:
        pass
    except Exception as e:
        log_error(f"help error: {e}")

# ═══════════════════════════════════════════════════════════════
#                      STARTUP & SHUTDOWN
# ═══════════════════════════════════════════════════════════════

async def startup():
    """Bot startup tasks"""
    try:
        me = await app.get_me()
        
        keys_count = len(get_all_gemini_keys())
        vips_count = vips_db.count_documents({})
        stickers_count = len(get_all_stickers())
        status = "🟢 ACTIVE" if is_bot_active() else "🔴 INACTIVE"
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║              🤖 ARYAN'S USERBOT STARTED 🤖                   ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  👤 User: {me.first_name} (@{me.username or 'N/A'})
║  🆔 ID: {me.id}
║                                                              ║
║  📊 Status: {status}
║  🔑 Gemini Keys: {keys_count}
║  👑 VIPs: {vips_count}
║  📎 Stickers: {stickers_count}
║                                                              ║
║  ✅ All systems operational!                                 ║
║  💡 Use /boton to activate                                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        log_action("Bot started successfully")
        await send_log(f"🚀 Bot started!\n\n👤 {me.first_name}\n📊 {status}")
        
    except Exception as e:
        logger.error(f"Startup error: {e}")

async def shutdown():
    """Bot shutdown tasks"""
    try:
        log_action("Bot shutting down")
        await send_log("🔴 Bot shutting down...")
    except:
        pass

# ═══════════════════════════════════════════════════════════════
#                      MAIN
# ═══════════════════════════════════════════════════════════════

async def main():
    """Main entry point"""
    try:
        await app.start()
        await startup()
        logger.info("Bot is running... Press Ctrl+C to stop")
        await idle()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
    finally:
        await shutdown()
        await app.stop()
        logger.info("Bot stopped")

if __name__ == "__main__":
    print("\n🚀 Starting Aryan's Userbot...\n")
    app.run(main())
