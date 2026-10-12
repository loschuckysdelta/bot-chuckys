
import os
import telebot

from main.start import registrar_start
from main.botones import registrar_botones
from main.guardar import registrar_guardar
from main.alerta import registrar_alerta
from main.vaucher import registrar_vaucher
from main.reportes import registrar_reportes

# NUEVO: SISTEMA VIP
from main.vip import register_vip


# ============================================================
# CONFIGURACIÓN
# ============================================================

TOKEN = os.environ["8849210272:AAE84XFogP1KwSy3NkZR1OpAASanLxWtVr0"]

bot = telebot.TeleBot(
    TOKEN,
    parse_mode="HTML"
)


# ============================================================
# REGISTRAR MÓDULOS
# ============================================================

registrar_start(bot)
registrar_botones(bot)
registrar_guardar(bot)
registrar_alerta(bot)
registrar_vaucher(bot)
registrar_reportes(bot)

# NUEVO: REGISTRAR SISTEMA VIP
register_vip(bot)


# ============================================================
# INICIAR BOT
# ============================================================

if __name__ == "__main__":

    print("🤖 BOT INICIADO")
    print("👑 SISTEMA VIP ACTIVADO")

    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30,
        allowed_updates=[
            "message",
            "callback_query",
            "chat_member"
        ]
    )
