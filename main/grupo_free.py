import requests
import telebot


# ============================================================
# CONFIGURACIÓN
# ============================================================

ID_GRUPO = -1004286061167
API_URL = "https://bot-apis-zkmk.vercel.app/api/contactos"


# ============================================================
# GRUPO FREE
# ============================================================

def ejecutar_grupo_free(bot, call):

    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    user_id = call.from_user.id

    # ========================================================
    # 1. VERIFICAR SI YA ESTÁ DENTRO DEL GRUPO
    # ========================================================

    try:

        miembro = bot.get_chat_member(
            chat_id=ID_GRUPO,
            user_id=user_id
        )

        if miembro.status in [
            "member",
            "administrator",
            "creator"
        ]:

            bot.send_message(
                user_id,
                "⚠️ <b>Ya eres miembro de este grupo.</b>\n\n"
                "No es necesario solicitar un nuevo enlace de acceso.",
                parse_mode="HTML"
            )

            return

    except Exception as e:
        print(f"⚠️ Error verificando miembro: {e}")

    # ========================================================
    # 2. BOTÓN PARA COMPARTIR CONTACTO
    # ========================================================

    markup = telebot.types.ReplyKeyboardMarkup(
        one_time_keyboard=True,
        resize_keyboard=True,
        input_field_placeholder="Presiona el botón de abajo 👇"
    )

    boton_contacto = telebot.types.KeyboardButton(
        text="📱 Compartir mi número telefónico",
        request_contact=True
    )

    markup.add(boton_contacto)

    # ========================================================
    # 3. PROCESAR CONTACTO
    # ========================================================

    def procesar_contacto(message):

        if message.chat.type != "private":
            return

        # ----------------------------------------------------
        # VERIFICAR QUE ENVÍE CONTACTO
        # ----------------------------------------------------

        if not message.contact:

            bot.send_message(
                user_id,
                "❌ Debes presionar el botón "
                "<b>📱 Compartir mi número telefónico</b>.",
                parse_mode="HTML",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )

            return

        # ----------------------------------------------------
        # VERIFICAR QUE SEA SU PROPIO NÚMERO
        # ----------------------------------------------------

        if (
            message.contact.user_id
            and message.contact.user_id != message.from_user.id
        ):

            bot.send_message(
                user_id,
                "❌ Debes compartir <b>tu propio número telefónico</b> "
                "utilizando el botón.",
                parse_mode="HTML",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )

            return

        # ====================================================
        # DATOS DEL USUARIO
        # ====================================================

        numero = message.contact.phone_number or ""
        nombre = message.from_user.first_name or ""

        apellido = message.from_user.last_name or ""

        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else "Sin username"
        )

        nombre_completo = f"{nombre} {apellido}".strip()

        # ====================================================
        # FORMATO QUE ESPERA TU API
        #
        # Ejemplo:
        # 51999999999 | Lenin | @usuario | 123456789
        # ====================================================

        linea = (
            f"{numero} | "
            f"{nombre_completo} | "
            f"{username} | "
            f"{user_id}"
        )

        payload = {
            "lineas": linea
        }

        print("📤 Enviando a API:")
        print(payload)

        # ====================================================
        # 4. GUARDAR EN API
        # ====================================================

        try:

            respuesta = requests.post(
                API_URL,
                json=payload,
                timeout=10
            )

            print(
                f"📡 API contactos → "
                f"{respuesta.status_code}: {respuesta.text}"
            )

            # Si la API da error, detener
            if not respuesta.ok:

                bot.send_message(
                    user_id,
                    "❌ <b>No se pudo registrar tu contacto.</b>\n\n"
                    "Inténtalo nuevamente.",
                    parse_mode="HTML",
                    reply_markup=telebot.types.ReplyKeyboardRemove()
                )

                return

        except requests.exceptions.Timeout:

            print("❌ Timeout conectando con API contactos")

            bot.send_message(
                user_id,
                "❌ El servidor tardó demasiado en responder.\n"
                "Inténtalo nuevamente.",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )

            return

        except requests.exceptions.RequestException as e:

            print(f"❌ Error API contactos: {e}")

            bot.send_message(
                user_id,
                "❌ No se pudo conectar con el servidor.",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )

            return

        # ====================================================
        # 5. CREAR ENLACE ÚNICO
        # ====================================================

        try:

            link_temporal = bot.create_chat_invite_link(
                chat_id=ID_GRUPO,
                member_limit=1,
                name=f"FREE-{user_id}"
            )

            bot.send_message(
                user_id,

                "✅ <b>NÚMERO VERIFICADO CORRECTAMENTE</b>\n\n"

                f"👤 <b>Usuario:</b> {nombre_completo}\n"
                f"📱 <b>Teléfono:</b> {numero}\n\n"

                "👥 <b>Acceso al Grupo Free</b>\n\n"

                f"🔗 {link_temporal.invite_link}\n\n"

                "⚠️ <i>Este enlace es personal y solamente puede "
                "utilizarse una vez.</i>",

                parse_mode="HTML",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )

        except Exception as e:

            print(f"❌ Error creando enlace: {e}")

            bot.send_message(
                user_id,

                "❌ <b>No se pudo generar el enlace.</b>\n\n"
                "El bot debe ser administrador del grupo y tener "
                "permiso para invitar usuarios.",

                parse_mode="HTML",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )

    # ========================================================
    # SOLICITAR CONTACTO
    # ========================================================

    msg = bot.send_message(

        user_id,

        "👥 <b>UNIRSE AL GRUPO FREE</b>\n\n"

        "Para obtener tu enlace de acceso debes verificar "
        "tu número telefónico.\n\n"

        "👇 Presiona el botón de abajo para compartir "
        "<b>tu propio número</b>.",

        parse_mode="HTML",
        reply_markup=markup
    )

    bot.register_next_step_handler(
        msg,
        procesar_contacto
    )