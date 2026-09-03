import telebot

from main.start import registrar_start
from main.botones import registrar_botones
from main.guardar import registrar_guardar
from main.alerta import registrar_alerta
from main.vaucher import registrar_vaucher


TOKEN = "8849210272:AAG5tPxo-Zq2eHyI_EETmZB7wCPfWGPxcZw"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


registrar_start(bot)
registrar_botones(bot)
registrar_guardar(bot)
registrar_alerta(bot)
registrar_vaucher(bot)


print("🤖 BOT INICIADO")

bot.infinity_polling()