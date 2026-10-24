"""Control de uso de comandos en grupos: exige acceso al chat privado.

Telegram no ofrece una lista de usuarios que bloquearon el bot. Esta
comprobacion intenta una accion privada sin enviar mensajes nuevos.
"""
import time
from threading import Lock

from telebot.handler_backends import ContinueHandling
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

_AVISOS = {}
_LOCK = Lock()
_ESPERA_AVISO = 90  # segundos entre avisos al mismo usuario por grupo


def registrar_verificacion_privado(bot):
    """Registrar ANTES que el resto de manejadores de comandos."""
    usuario_bot = bot.get_me().username

    @bot.message_handler(
        func=lambda m: (
            m.chat.type in ("group", "supergroup")
            and bool(m.text)
            and m.text.startswith("/")
        ),
        content_types=["text"],
    )
    def comprobar_privado(message):
        usuario = message.from_user
        if not usuario or usuario.is_bot:
            return ContinueHandling()

        # No enviar un DM invasivo: comprueba si Telegram acepta una
        # accion de chat privado. Puede fallar si nunca pulsó /start.
        try:
            bot.send_chat_action(usuario.id, "typing")
        except Exception as exc:
            # Telegram puede rechazar la accion por bloqueo, por no haber
            # iniciado el chat o por restricciones/transitorios.
            ahora = time.monotonic()
            llave = (message.chat.id, usuario.id)
            with _LOCK:
                ultimo = _AVISOS.get(llave, 0)
                mostrar = (ahora - ultimo) >= _ESPERA_AVISO
                if mostrar:
                    _AVISOS[llave] = ahora
                # Evitar crecimiento ilimitado con muchos usuarios.
                if len(_AVISOS) > 5000:
                    _AVISOS.clear()
            if mostrar:
                teclado = InlineKeyboardMarkup()
                teclado.add(InlineKeyboardButton(
                    "🔓 Desbloquear / Iniciar bot",
                    url=f"https://t.me/{usuario_bot}?start=verificar",
                ))
                try:
                    bot.reply_to(
                        message,
                        "🔒 Para utilizar comandos de este grupo, primero debes "
                        "desbloquearme en Telegram y abrir mi chat privado. "
                        "Pulsa <b>Iniciar</b> y luego repite el comando aquí.\n\n"
                        "ℹ️ Si todavía no me has iniciado, también debes hacerlo.",
                        reply_markup=teclado,
                    )
                except Exception as aviso_error:
                    print(f"No se pudo mostrar aviso de verificación: {aviso_error}")
            print(f"Acceso privado no disponible para {usuario.id}: {exc}")
            # No deja pasar el comando a otros handlers.
            return

        # Continuar la ejecución normal del comando existente.
        return ContinueHandling()
