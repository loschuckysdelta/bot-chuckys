
import os
import telebot
from telebot.apihelper import ApiTelegramException

from main.start import registrar_start
from main.botones import registrar_botones
from main.grupo_free import registrar_canje_free
from main.guardar import registrar_guardar
from main.alerta import registrar_alerta
from main.vaucher import registrar_vaucher
from main.reportes import registrar_reportes
from main.vip import register_vip
from main.grupo_vip import registrar_planes_vip
from main.verificar_privado import registrar_verificacion_privado

# ============================================================
# CONFIGURACIÓN DEL BOT
# ============================================================

TOKEN = os.getenv(
    "BOT_TOKEN",
    "9147624464:AAFCLBMMH0ZK0qA_Q9LWcc2hfW4A3Oe6S_Q"

).strip()

if not TOKEN or TOKEN == "PEGA_AQUI_TU_TOKEN_NUEVO":
    print("❌ CONFIGURA TU NUEVO TOKEN DE BOTFATHER")
    raise SystemExit(1)

bot = telebot.TeleBot(
    TOKEN,
    parse_mode="HTML"
)

# ============================================================
# INICIAR BOT
# ============================================================

if __name__ == "__main__":

    # Verificar token antes de registrar módulos
    try:
        info = bot.get_me()
        print(f"✅ BOT AUTORIZADO: @{info.username}")

    except ApiTelegramException as error:
        print(f"❌ TOKEN RECHAZADO POR TELEGRAM: {error}")
        raise SystemExit(1)

    # Verificar acceso al chat privado antes de ejecutar comandos de grupos
    registrar_verificacion_privado(bot)

    # Registrar sistema VIP
    register_vip(bot)
    print("👑 SISTEMA VIP REGISTRADO")

    # Registrar módulos existentes
    registrar_start(bot)
    registrar_botones(bot)
    registrar_canje_free(bot)  # Activar botón CANJEAR MI KEY
    registrar_planes_vip(bot)
    registrar_guardar(bot)
    registrar_alerta(bot)
    registrar_vaucher(bot)
    registrar_reportes(bot)

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
