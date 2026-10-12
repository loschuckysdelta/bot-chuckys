import telebot
from main.start import registrar_start
from main.botones import registrar_botones
from main.guardar import registrar_guardar
from main.alerta import registrar_alerta
from main.vaucher import registrar_vaucher
from main.reportes import registrar_reportes
from main.vip import register_vip


# ============================================================
# CONFIGURACIÓN DEL BOT
# ============================================================

# Coloca aquí tu nuevo token de BotFather
TOKEN = "8849210272:AAEfhBFlsP-ll0qthfor-FQAa8wrTcHMjbc"

bot = telebot.TeleBot(
    TOKEN,
    parse_mode="HTML"
)


# ============================================================
# REGISTRAR SISTEMA VIP PRIMERO
# ============================================================

register_vip(bot)

print("👑 SISTEMA VIP REGISTRADO")


# ============================================================
# REGISTRAR MÓDULOS EXISTENTES
# ============================================================

registrar_start(bot)
registrar_botones(bot)
registrar_guardar(bot)
registrar_alerta(bot)
registrar_vaucher(bot)
registrar_reportes(bot)


# ============================================================
# INICIAR BOT
# ============================================================

if __name__ == "__main__":

    print("=" * 45)
    print("🤖 BOT LOS CHUCKYS INICIADO")
    print("👑 SISTEMA VIP ACTIVADO")
    print("🌐 API: bot-apis-zkmk.vercel.app")
    print("=" * 45)

    try:
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

    except KeyboardInterrupt:
        print("🛑 BOT DETENIDO")

    except Exception as error:
        print(f"❌ ERROR DEL BOT: {error}")
        raise
