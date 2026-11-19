import html
import requests

from telebot.apihelper import ApiTelegramException
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_URL = "https://bot-apis-zkmk.vercel.app"

# ID de tu canal
CANAL_ID = -1003958891359

# Enlace de tu canal (público o de invitación privado)
CANAL_URL = "https://t.me/+jVZ-ruZi-Ac1ODA5"

# URL directa de imagen para el menú principal
URL_IMAGEN_MENU = "https://i.postimg.cc/Cxgrn1NW/image.png"


# ============================================================
# VERIFICAR SI ESTÁ EN EL CANAL
# ============================================================

def esta_en_canal(bot, user_id):
    try:
        miembro = bot.get_chat_member(CANAL_ID, user_id)
        estados_permitidos = {"creator", "administrator", "member"}
        return miembro.status in estados_permitidos

    except ApiTelegramException as e:
        print(
            f"[CANAL] Error verificando usuario {user_id}: "
            f"{e.error_code} - {e.description}"
        )
        return False

    except Exception as e:
        print(f"[CANAL] Error inesperado verificando usuario {user_id}: {e}")
        return False


# ============================================================
# BOTONERA PARA UNIRSE
# ============================================================

def botonera_unirse():
    teclado = InlineKeyboardMarkup(row_width=1)

    teclado.add(
        InlineKeyboardButton(
            "📢 UNIRME AL CANAL",
            url=CANAL_URL
        )
    )

    teclado.add(
        InlineKeyboardButton(
            "✅ VERIFICAR",
            callback_data="verificar_canal"
        )
    )

    return teclado


# ============================================================
# MENSAJE DE CANAL OBLIGATORIO
# ============================================================

def mensaje_unirse(bot, chat_id):
    texto = (
        "🚨 <b>ACCESO RESTRINGIDO</b>\n\n"
        "Para utilizar este bot debes pertenecer "
        "obligatoriamente a nuestro canal de Telegram.\n\n"
        "1️⃣ Pulsa <b>UNIRME AL CANAL</b>\n"
        "2️⃣ Únete al canal\n"
        "3️⃣ Regresa al bot\n"
        "4️⃣ Pulsa <b>✅ VERIFICAR</b>\n\n"
        "🔒 Mientras no estés unido, "
        "<b>las funciones del bot permanecerán bloqueadas.</b>"
    )

    try:
        bot.send_message(
            chat_id,
            texto,
            parse_mode="HTML",
            reply_markup=botonera_unirse()
        )
    except ApiTelegramException as e:
        if e.error_code != 403:
            print(f"[TELEGRAM] Error enviando mensaje de canal: {e.error_code} - {e.description}")
    except Exception as e:
        print(f"[BOT] Error enviando mensaje de canal: {e}")


# ============================================================
# BOTONERA PRINCIPAL
# ============================================================

def botonera_principal():
    teclado = InlineKeyboardMarkup(row_width=2)

    # FILA 1
    teclado.row(
        InlineKeyboardButton(
            "👥 GRUPO FREE",
            callback_data="grupo_free"
        ),
        InlineKeyboardButton(
            "👑 GRUPO VIP",
            callback_data="grupo_vip"
        )
    )

    # FILA 2
    teclado.row(
        InlineKeyboardButton(
            "💚 YAPE FREE",
            callback_data="yape_free"
        ),
        InlineKeyboardButton(
            "📱 YAPE APP",
            callback_data="yape_app"
        )
    )

    # FILA 3
    teclado.row(
        InlineKeyboardButton(
            "📋 MENÚ FREE",
            callback_data="menu_free"
        ),
        InlineKeyboardButton(
            "🤖 BOT YAPE FREE",
            callback_data="bot_yape_free"
        )
    )

    return teclado


# ============================================================
# REGISTRAR / ACTUALIZAR USUARIO
# ============================================================

def registrar_usuario_api(usuario):
    if not usuario:
        return None

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

        if not respuesta.ok:
            print(
                f"[API] Respuesta no exitosa ({respuesta.status_code}) "
                f"para usuario {usuario.id}: {respuesta.text}"
            )

        return respuesta

    except requests.RequestException as e:
        print(f"[API] Error registrando usuario {usuario.id}: {e}")
        return None

    except Exception as e:
        print(f"[API] Error inesperado registrando usuario {usuario.id}: {e}")
        return None


# ============================================================
# MOSTRAR MENÚ PRINCIPAL
# ============================================================

def mostrar_menu(bot, chat_id, usuario):
    nombre_seguro = html.escape(usuario.first_name or "Usuario")

    caption = (
        "🏠 <b>MENÚ PRINCIPAL</b>\n\n"
        f"👤 Bienvenido <b>{nombre_seguro}</b>\n\n"
        "✅ Membresía verificada\n\n"
        "👇 <b>Selecciona una opción:</b>"
    )

    try:
        bot.send_photo(
            chat_id,
            photo=URL_IMAGEN_MENU,
            caption=caption,
            parse_mode="HTML",
            reply_markup=botonera_principal()
        )
    except ApiTelegramException as e:
        if e.error_code == 403:
            # Usuario bloqueó el bot
            return

        if e.error_code != 400:
            print(f"[TELEGRAM] Error de imagen del menú: {e.error_code} - {e.description}")

        try:
            bot.send_message(
                chat_id,
                caption,
                parse_mode="HTML",
                reply_markup=botonera_principal()
            )
        except Exception as send_error:
            print(f"[TELEGRAM] No se pudo enviar menú de texto: {send_error}")

    except Exception as e:
        print(f"[BOT] Error mostrando menú: {e}")


# ============================================================
# COMANDO /START Y VERIFICACIÓN
# ============================================================

def registrar_start(bot):

    @bot.message_handler(commands=["start"], chat_types=["private"])
    def start(message):
        registrar_usuario_api(message.from_user)

        user_id = message.from_user.id

        if not esta_en_canal(bot, user_id):
            mensaje_unirse(bot, message.chat.id)
            return

        mostrar_menu(bot, message.chat.id, message.from_user)

    @bot.callback_query_handler(func=lambda call: call.data == "verificar_canal")
    def verificar_canal(call):
        user_id = call.from_user.id

        if esta_en_canal(bot, user_id):
            registrar_usuario_api(call.from_user)

            try:
                bot.answer_callback_query(
                    call.id,
                    "✅ Verificación completada",
                    show_alert=False
                )
            except Exception as e:
                print(f"[TELEGRAM] Error respondiendo callback: {e}")

            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass

            mostrar_menu(bot, call.message.chat.id, call.from_user)
            return

        try:
            bot.answer_callback_query(
                call.id,
                (
                    "🚨 Todavía no perteneces al canal.\n\n"
                    "Únete primero y vuelve a verificar."
                ),
                show_alert=True
            )
        except Exception as e:
            print(f"[TELEGRAM] Error enviando alerta de verificación: {e}")
