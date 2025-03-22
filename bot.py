import os
import telebot
from dotenv import load_dotenv
from flask import Flask

# Load token from .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

# Handle /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome!")

# Handle all other messages
@bot.message_handler(func=lambda message: True)
def send_hello(message):
    bot.reply_to(message, "hello")

# Start the bot in a separate thread
import threading
bot_thread = threading.Thread(target=bot.infinity_polling)
bot_thread.start()

# Create a simple web server to keep Render happy
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
