import os
import telebot
from dotenv import load_dotenv

# Load token from .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(func=lambda message: True)
def send_hello(message):
    bot.reply_to(message, "hello")

# Keep the bot running
bot.infinity_polling()
