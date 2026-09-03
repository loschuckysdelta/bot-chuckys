import requests

from telebot.apihelper import ApiTelegramException
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_URL = "https://bot-apis-zkmk.vercel.app"

# ID de tu canal
CANAL_ID = -1003691254516

# IMPORTANTE:
# Cambia esto por el enlace REAL de tu canal.
# Ejemplo:
# CANAL_URL = "https://t.me/LosChuckys"
#
# Si el canal es privado, coloca el enlace de invitación:
# CANAL_URL = "https://t.me/+xxxxxxxxxxxx"
CANAL_URL = "https://t.me/loschuckys_pe"


# ============================================================
# VERIFICAR SI ESTÁ EN EL CANAL
# ============================================================

def esta_en_canal(bot, user_id):
    try:

        miembro = bot.get_chat_member(
            CANAL_ID,
            user_id
        )

        # Estados que SÍ tienen acceso
        estados_permitidos = [
            "creator",
            "administrator",
            "member"
        ]

        return miembro.status in estados_permitidos

    except ApiTelegramException as e:

        print(
            f"[CANAL] Error verificando usuario {user_id}: "
            f"{e.error_code} - {e.description}"
        )

        return False

    except Exception as e:

        print(
            f"[CANAL] Error inesperado: {e}"
        )

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

    except ApiTelegramException:
        pass

    except Exception:
        pass


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

    except requests.RequestException as e:

        print(
            f"[API] Error registrando usuario: {e}"
        )

        return None

    except Exception as e:

        print(
            f"[API] Error inesperado: {e}"
        )

        return None


# ============================================================
# MOSTRAR MENÚ PRINCIPAL
# ============================================================

def mostrar_menu(bot, chat_id, usuario):

    # USA URL DIRECTA DE IMAGEN
    #
    # Tu anterior:
    # https://postimg.cc/GHXxZb6Q
    #
    # NO es una URL directa de imagen.
    #
    # Debe ser algo parecido a:
    # https://i.postimg.cc/xxxxxx/imagen.png

    url_imagen = "https://i.postimg.cc/Cxgrn1NW/image.png"

    nombre = usuario.first_name or "Usuario"

    caption = (
        "🏠 <b>MENÚ PRINCIPAL</b>\n\n"
        f"👤 Bienvenido <b>{nombre}</b>\n\n"
        "✅ Membresía verificada\n\n"
        "👇 <b>Selecciona una opción:</b>"
    )

    try:

        bot.send_photo(
            chat_id,
            photo=url_imagen,
            caption=caption,
            parse_mode="HTML",
            reply_markup=botonera_principal()
        )

    except ApiTelegramException as e:

        # Si falla la imagen enviamos solamente texto
        if e.error_code == 400:

            try:

                bot.send_message(
                    chat_id,
                    caption,
                    parse_mode="HTML",
                    reply_markup=botonera_principal()
                )

            except Exception:
                pass

        elif e.error_code == 403:
            # Usuario bloqueó el bot
            pass

        else:

            print(
                f"[TELEGRAM] Error mostrando menú: "
                f"{e.error_code} - {e.description}"
            )

    except Exception as e:

        print(
            f"[BOT] Error mostrando menú: {e}"
        )


# ============================================================
# COMANDO /START
# ============================================================

def registrar_start(bot):

    # ========================================================
    # /START
    # ========================================================

    @bot.message_handler(
        commands=["start"],
        chat_types=["private"]
    )
    def start(message):

        # Registrar / actualizar usuario
        registrar_usuario_api(message)

        user_id = message.from_user.id

        # ----------------------------------------------------
        # COMPROBAR CANAL
        # ----------------------------------------------------

        if not esta_en_canal(
            bot,
            user_id
        ):

            mensaje_unirse(
                bot,
                message.chat.id
            )

            return

        # ----------------------------------------------------
        # USUARIO VERIFICADO
        # ----------------------------------------------------

        mostrar_menu(
            bot,
            message.chat.id,
            message.from_user
        )


    # ========================================================
    # BOTÓN VERIFICAR
    # ========================================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "verificar_canal"
    )
    def verificar_canal(call):

        user_id = call.from_user.id

        # ----------------------------------------------------
        # YA ESTÁ EN EL CANAL
        # ----------------------------------------------------

        if esta_en_canal(
            bot,
            user_id
        ):

            try:

                bot.answer_callback_query(
                    call.id,
                    "✅ Verificación completada",
                    show_alert=False
                )

            except Exception:
                pass

            # Borrar alerta anterior
            try:

                bot.delete_message(
                    call.message.chat.id,
                    call.message.message_id
                )

            except Exception:
                pass

            # Mostrar menú
            mostrar_menu(
                bot,
                call.message.chat.id,
                call.from_user
            )

            return

        # ----------------------------------------------------
        # TODAVÍA NO ESTÁ EN EL CANAL
        # ----------------------------------------------------

        try:

            bot.answer_callback_query(
                call.id,
                (
                    "🚨 Todavía no perteneces al canal.\n\n"
                    "Únete primero y vuelve a verificar."
                ),
                show_alert=True
            )

        except Exception:
            pass