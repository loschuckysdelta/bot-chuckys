import telebot

from main.start import registrar_start
from main.botones import registrar_botones


TOKEN = "8849210272:AAG5tPxo-Zq2eHyI_EETmZB7wCPfWGPxcZw"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


registrar_start(bot)
registrar_botones(bot)


print("🤖 BOT INICIADO")

bot.infinity_polling()