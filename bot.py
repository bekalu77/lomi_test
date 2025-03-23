import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from dotenv import load_dotenv
import sqlite3
import time
import threading

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Ensure ADMIN_GROUP_ID and CHANNEL_ID are integers
try:
    ADMIN_GROUP_ID = int(ADMIN_GROUP_ID)
    CHANNEL_ID = int(CHANNEL_ID)
except (ValueError, TypeError) as e:
    print(f"Error: Invalid chat ID. ADMIN_GROUP_ID and CHANNEL_ID must be integers. Error: {e}")
    exit(1)

# Initialize bot with increased timeout
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=5)

# Debugging: Print chat IDs
print(f"ADMIN_GROUP_ID: {ADMIN_GROUP_ID}")
print(f"CHANNEL_ID: {CHANNEL_ID}")

# Test sending a message to ADMIN_GROUP_ID
try:
    bot.send_message(ADMIN_GROUP_ID, "Bot started successfully!")
except telebot.apihelper.ApiTelegramException as e:
    print(f"Error sending message to ADMIN_GROUP_ID: {e}")
    exit(1)

# User-facing texts (Amharic)
TEXTS = {
    "welcome": "እንኳን ደና መጡ! እባክዎ የፁሁፏን ይዘት ይምረጡ",
    "category_selected": "አሁን መፃፋ ይጀምሩ 🗒️🖊️፣ ሲጨርሱ ፁህፉወ ወደ ሳንሱር ይላካል። 📌 ልብ ይበሉ; ካስፈለገ አንድ አንድ ፎቶ ብቻ ይጠቀሙ። መልካም ግዜ",
    "no_category": "ለፁህፉወ ምንም ይዘት አልመረጡም፣ እንደገና ለመጀመር /start ይጫኑ",
    "unsupported_format": "⚠️ እባክወ ፎቶ ወይም ቪዲዬ ብቻ ይጠቀሙ እና እንደገና ይሞክሩ  /start",
    "too_many_pending": "⚠️ ለሳንሱር የተላኩ ብዙ ፁህፎች ስላልወት ትንሽ ቆይተዉ ይሞክሩ",
    "text_too_long": "⚠️ ፁህፋዎ ከ 4000 ፊደላት በላይ �ለሆነ ድጋሚ አስተካክለዉ በ /start ይሞክሩ",
    "story_submitted": "ፁህፋወ ለሳንሱር ተልኳል፣ እባክወ በትግስት ይጠብቁ",
    "story_approved": "✅ ፁህፋወ በ @lomi_reads ቻናል ላይ ተለጥፏል 🎉 ሌላ ለመፃፍ /start ብለዉ ይጀምሩ",
    "story_rejected": "❌ ፁሁፍወ ሳንሱር አላለፈም እንደገና ይሞክሩ /start .",
    "media_group_warning": "⚠️እባክወ በአንድ ፁህፋ ከ አንድ በላይ ፎቶ ወይም ቪዲዬ አይጠቀሙ እና እንደገና ይሞክሩ /start",
    "pending_limit": "⚠️ ለሳንሱር የተላኩ ብዙ ፁህፎች ስላልወት ትንሽ ቆይተዉ ይሞክሩ",
    "error_occurred": "⚠️ የሢሥተም ችግር አጋጥሟል። እባክዎ ትንሽ ቆይተዉ ይሞክሩ",
    "write_command": "📝 እባክዎ የፁሁፍዎን ይዘት ለመላክ /write ይጠቀሙ።",
    "write_reminder": "⚠️ እባክዎ የፁሁፍዎን ይዘት ለመላክ /write ይጠቀሙ።",
}

# Define categories for user selection
CATEGORIES = {
    "real": "እዉነተኛ ታሪክ ወይም አጋጣሚ",
    "fiction": "ልብ ወልድ ታሪኮች",
    "joke": "አጫጭር ቀልዶች",
    "celebrity": "ታዋቂ ሰውችን በተመለከተ",
    "news": "ዜና",
    "politics": "ፖለቲካ",
    "personal_opinion": "የግል ምልከታ",
    "public_info": "ለማህበረቡ ጥቆማ",
    "others": "ሌሎች ታሪኮች",
}

# Dictionary to buffer media group messages
media_buffer = {}

# Track user states
user_states = {}

# Database setup
class DatabaseConnection:
    def __enter__(self):
        self.conn = sqlite3.connect("bot_data.db", check_same_thread=False)
        return self.conn.cursor()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.commit()
        self.conn.close()

# Initialize database tables
with DatabaseConnection() as cursor:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        post_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category TEXT,
        status TEXT DEFAULT 'pending'
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        category TEXT,
        last_activity REAL DEFAULT (strftime('%s', 'now'))
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS media (
        media_id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        file_id TEXT,
        type TEXT)
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS text_content (
        post_id INTEGER PRIMARY KEY,
        content TEXT)
    """)

# Helper functions
def add_hashtag(text, category):
    hashtag = f"#{category}"
    return f"{text}\n\n{hashtag}" if text and hashtag not in text else text

def register_user(user_id):
    with DatabaseConnection() as cursor:
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))

def process_media_group(media_group_id):
    if media_group_id not in media_buffer:
        return

    data = media_buffer.pop(media_group_id)
    messages, user_id, category = data['messages'], data['user_id'], data['category']
    
    # Check media count
    media_count = sum(1 for msg in messages if msg.content_type in ['photo', 'video'])
    if media_count > 1:
        bot.send_message(user_id, TEXTS["media_group_warning"])
        return

    # Process valid submission
    with DatabaseConnection() as cursor:
        cursor.execute("INSERT INTO posts (user_id, category) VALUES (?, ?)", (user_id, category))
        post_id = cursor.lastrowid

        text_content = None
        for msg in messages:
            if msg.content_type in ['photo', 'video']:
                file_id = msg.photo[-1].file_id if msg.content_type == 'photo' else msg.video.file_id
                cursor.execute("INSERT INTO media (post_id, file_id, type) VALUES (?, ?, ?)", 
                              (post_id, file_id, msg.content_type))
                if msg.caption:
                    text_content = msg.caption
            elif msg.text:
                text_content = msg.text

        if text_content:
            cursor.execute("INSERT INTO text_content (post_id, content) VALUES (?, ?)", 
                          (post_id, add_hashtag(text_content, category)))

    # Notify admins
    send_for_review(post_id, [m for m in messages if m.content_type in ['photo', 'video']], text_content)
    bot.send_message(user_id, TEXTS["story_submitted"])

def send_for_review(post_id, media_messages, text):
    try:
        media_group = []
        for idx, msg in enumerate(media_messages):
            media = InputMediaPhoto(msg.photo[-1].file_id) if msg.content_type == 'photo' else InputMediaVideo(msg.video.file_id)
            if idx == 0 and text:
                media.caption = text
            media_group.append(media)
        
        if media_group:
            bot.send_media_group(ADMIN_GROUP_ID, media_group)
        elif text:
            bot.send_message(ADMIN_GROUP_ID, text)

        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{post_id}"),
                   InlineKeyboardButton("❌ Reject", callback_data=f"reject_{post_id}"))
        bot.send_message(ADMIN_GROUP_ID, "Please review the submission:", reply_markup=markup)
    except Exception as e:
        print(f"Error in send_for_review: {e}")

# Handlers
@bot.message_handler(commands=['start'])
def start(message):
    register_user(message.chat.id)
    markup = InlineKeyboardMarkup()
    [markup.add(InlineKeyboardButton(v, callback_data=k)) for k, v in CATEGORIES.items()]
    bot.send_message(message.chat.id, TEXTS["welcome"], reply_markup=markup)

@bot.message_handler(commands=['write'])
def write(message):
    user_id = message.chat.id
    user_states[user_id] = "writing"
    markup = InlineKeyboardMarkup()
    [markup.add(InlineKeyboardButton(v, callback_data=k)) for k, v in CATEGORIES.items()]
    bot.send_message(user_id, TEXTS["category_selected"], reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in CATEGORIES.keys())
def set_category(call):
    user_id = call.message.chat.id
    category = call.data
    with DatabaseConnection() as cursor:
        cursor.execute("UPDATE users SET category = ? WHERE user_id = ?", (category, user_id))
    bot.send_message(user_id, TEXTS["category_selected"])
    user_states[user_id] = "writing"  # Allow user to submit content

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) != "writing")
def remind_to_write(message):
    bot.send_message(message.chat.id, TEXTS["write_reminder"])

@bot.message_handler(content_types=['text', 'photo', 'video'], func=lambda message: user_states.get(message.chat.id) == "writing")
def handle_submission(message):
    user_id = message.chat.id
    
    with DatabaseConnection() as cursor:
        cursor.execute("SELECT category FROM users WHERE user_id = ?", (user_id,))
        category = cursor.fetchone()
        
        if not category or not category[0]:
            bot.send_message(user_id, TEXTS["no_category"])
            return
        
        cursor.execute("SELECT post_id FROM posts WHERE user_id = ? AND status = 'pending'", (user_id,))
        if len(cursor.fetchall()) >= 3:
            bot.send_message(user_id, TEXTS["pending_limit"])
            return

    # Handle media groups
    if message.media_group_id:
        mgid = message.media_group_id
        if mgid not in media_buffer:
            media_buffer[mgid] = {
                'messages': [],
                'user_id': user_id,
                'category': category[0],
                'timer': threading.Timer(1.0, process_media_group, [mgid])
            }
            media_buffer[mgid]['timer'].start()
        media_buffer[mgid]['messages'].append(message)
        return

    # Handle single submission
    with DatabaseConnection() as cursor:
        cursor.execute("INSERT INTO posts (user_id, category) VALUES (?, ?)", (user_id, category[0]))
        post_id = cursor.lastrowid

        text_content = message.caption or message.text
        if text_content:
            cursor.execute("INSERT INTO text_content VALUES (?, ?)", 
                          (post_id, add_hashtag(text_content, category[0])))
        
        if message.content_type in ['photo', 'video']:
            file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.video.file_id
            cursor.execute("INSERT INTO media (post_id, file_id, type) VALUES (?, ?, ?)", 
                          (post_id, file_id, message.content_type))

    send_for_review(post_id, [message] if message.content_type in ['photo', 'video'] else [], text_content)
    bot.send_message(user_id, TEXTS["story_submitted"])
    user_states[user_id] = None  # Reset state after submission

@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
def handle_review(call):
    action, post_id = call.data.split('_')
    
    with DatabaseConnection() as cursor:
        cursor.execute("SELECT user_id, category FROM posts WHERE post_id = ? AND status = 'pending'", (post_id,))
        result = cursor.fetchone()
        if not result:
            return

        user_id, category = result
        cursor.execute("UPDATE posts SET status = ? WHERE post_id = ?", 
                      ('approved' if action == 'approve' else 'rejected', post_id))

        if action == 'approve':
            cursor.execute("SELECT content FROM text_content WHERE post_id = ?", (post_id,))
            text = cursor.fetchone()
            text = text[0] if text else f"#{category}"
            
            cursor.execute("SELECT file_id, type FROM media WHERE post_id = ?", (post_id,))
            media = cursor.fetchall()
            
            if media:
                media_group = [InputMediaPhoto(m[0]) if m[1] == 'photo' else InputMediaVideo(m[0]) for m in media]
                media_group[0].caption = text
                bot.send_media_group(CHANNEL_ID, media_group)
            else:
                bot.send_message(CHANNEL_ID, text)
            
            bot.send_message(user_id, TEXTS["story_approved"])
        else:
            bot.send_message(user_id, TEXTS["story_rejected"])

    bot.edit_message_reply_markup(ADMIN_GROUP_ID, call.message.message_id, reply_markup=None)
bot.remove_webhook()
# Start polling
bot.infinity_polling(timeout=60)  # Increased timeout to 60 seconds
