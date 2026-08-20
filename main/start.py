import requests

from telebot.apihelper import ApiTelegramException
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


# ============================================================
# CONFIGURACIÓN API
# ============================================================

BASE_URL = "https://bot-apis-zkmk.vercel.app"


# ============================================================
# BOTONERA PRINCIPAL
# ============================================================

def botonera_principal():
    teclado = InlineKeyboardMarkup(row_width=2)

    teclado.add(
        InlineKeyboardButton(
            "👥 GRUPO FREE",
            callback_data="grupo_free"
        ),
        InlineKeyboardButton(
            "👑 GRUPO VIP",
            callback_data="grupo_vip"
        ),
        InlineKeyboardButton(
            "💚 YAPE FREE",
            callback_data="yape_free"
        ),
        InlineKeyboardButton(
            "📱 YAPE APP",
            callback_data="yape_app"
        )
    )

    return teclado


# ============================================================
# REGISTRAR / ACTUALIZAR USUARIO
# ============================================================

def registrar_usuario_api(message):

    usuario = message.from_user

    datos = {
        "telegramId": usuario.id,
        "username": usuario.username or "",
        "nombre": usuario.first_name or "Usuario"
    }

    try:

        respuesta = requests.post(
            f"{BASE_URL}/api/users",
            json=datos,
            timeout=10
        )

        return respuesta

    except requests.RequestException:
        return None

    except Exception:
        return None


# ============================================================
# COMANDO /START (SOLO PRIVADO)
# ============================================================

def registrar_start(bot):

    # chat_types=["private"] asegura que solo responda al privado en este handler
    @bot.message_handler(commands=["start"], chat_types=["private"])
    def start(message):

        # ----------------------------------------------------
        # REGISTRAR / ACTUALIZAR USUARIO EN LA API
        # ----------------------------------------------------

        registrar_usuario_api(message)

        # ----------------------------------------------------
        # IMAGEN
        # ----------------------------------------------------

        url_imagen = "https://postimg.cc/GHXxZb6Q"

        caption = (
            "🏠 <b>MENÚ PRINCIPAL</b>\n\n"
            "👤 Bienvenido "
            f"<b>{message.from_user.first_name or 'Usuario'}</b>\n\n"
            "👇 <b>Selecciona una opción:</b>"
        )

        # ----------------------------------------------------
        # ENVIAR MENÚ CON IMAGEN
        # ----------------------------------------------------

        try:

            bot.send_photo(
                message.chat.id,
                photo=url_imagen,
                caption=caption,
                parse_mode="HTML",
                reply_markup=botonera_principal()
            )

        except ApiTelegramException as e:

            # ------------------------------------------------
            # SI TELEGRAM RECHAZA LA IMAGEN
            # ------------------------------------------------

            if e.error_code == 400:

                try:

                    bot.send_message(
                        message.chat.id,
                        caption,
                        parse_mode="HTML",
                        reply_markup=botonera_principal()
                    )

                except ApiTelegramException:
                    pass

            elif e.error_code == 403:
                pass

            else:
                pass

        except Exception:
            pass