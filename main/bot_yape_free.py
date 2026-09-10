import requests
import telebot


# ============================================================
# CONFIGURACIÓN
# ============================================================

ID_GRUPO = -1004401505861

API_URL = "https://bot-apis-zkmk.vercel.app/api/contactos"

IMAGEN_YAPE_FREE = "https://i.postimg.cc/ZKyM3jPQ/image.png"


# ============================================================
# BOT YAPE FREE
# ============================================================

def ejecutar_bot_yape_free(bot, call):

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
                "🤖 <b>BOT YAPE FREE</b>\n\n"
                "⚠️ <b>Ya eres miembro del grupo Yape Free.</b>\n\n"
                "No necesitas solicitar un nuevo enlace.",
                parse_mode="HTML"
            )
            return

    except Exception as e:
        print(f"⚠️ Error verificando miembro: {e}")

    # ========================================================
    # 2. BOTÓN PARA COMPARTIR TELÉFONO
    # ========================================================

    markup = telebot.types.ReplyKeyboardMarkup(
        one_time_keyboard=True,
        resize_keyboard=True,
        input_field_placeholder="Presiona el botón de abajo 👇"
    )

    boton_contacto = telebot.types.KeyboardButton(
        text="📱 Verificar mi número",
        request_contact=True
    )

    markup.add(boton_contacto)

    # ========================================================
    # 3. PROCESAR CONTACTO
    # ========================================================

    def procesar_contacto(message):

        if message.chat.type != "private":
            return

        # ====================================================
        # VALIDAR QUE HAYA ENVIADO CONTACTO
        # ====================================================

        if not message.contact:

            bot.send_message(
                user_id,
                "🤖 <b>BOT YAPE FREE</b>\n\n"
                "❌ Debes presionar el botón "
                "<b>📱 Verificar mi número</b>.",
                parse_mode="HTML",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
            return

        # ====================================================
        # VALIDAR QUE SEA SU PROPIO CONTACTO
        # ====================================================

        if (
            message.contact.user_id
            and message.contact.user_id != message.from_user.id
        ):

            bot.send_message(
                user_id,
                "🤖 <b>BOT YAPE FREE</b>\n\n"
                "❌ Debes compartir <b>tu propio número telefónico</b>.\n\n"
                "No puedes utilizar el contacto de otra persona.",
                parse_mode="HTML",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
            return

        # ====================================================
        # 4. DATOS DEL USUARIO
        # ====================================================

        numero = message.contact.phone_number or ""

        nombre = message.from_user.first_name or ""
        apellido = message.from_user.last_name or ""

        nombre_completo = f"{nombre} {apellido}".strip()

        username = message.from_user.username or ""

        # ====================================================
        # 5. JSON PARA LA API
        # ====================================================

        payload = {
            "telegramId": user_id,
            "username": username,
            "nombre": nombre_completo,
            "telefono": numero
        }

        print("=" * 60)
        print("📤 BOT YAPE FREE - ENVIANDO CONTACTO")
        print(payload)
        print("=" * 60)

        # ====================================================
        # 6. GUARDAR CONTACTO EN API
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

            if not respuesta.ok:

                bot.send_message(
                    user_id,
                    "🤖 <b>BOT YAPE FREE</b>\n\n"
                    "❌ <b>No se pudo registrar tu número.</b>\n\n"
                    "Inténtalo nuevamente.",
                    parse_mode="HTML",
                    reply_markup=telebot.types.ReplyKeyboardRemove()
                )
                return

        except requests.exceptions.Timeout:

            print("❌ Timeout en API contactos")

            bot.send_message(
                user_id,
                "🤖 <b>BOT YAPE FREE</b>\n\n"
                "❌ El servidor tardó demasiado en responder.\n\n"
                "Inténtalo nuevamente.",
                parse_mode="HTML",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
            return

        except requests.exceptions.RequestException as e:

            print(f"❌ Error API contactos: {e}")

            bot.send_message(
                user_id,
                "🤖 <b>BOT YAPE FREE</b>\n\n"
                "❌ No se pudo conectar con el servidor.",
                parse_mode="HTML",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
            return

        # ====================================================
        # 7. VOLVER A VERIFICAR SI YA ESTÁ EN EL GRUPO
        # ====================================================

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
                    "🤖 <b>BOT YAPE FREE</b>\n\n"
                    "✅ Tu número fue verificado correctamente.\n\n"
                    "⚠️ Pero ya perteneces al grupo Yape Free.",
                    parse_mode="HTML",
                    reply_markup=telebot.types.ReplyKeyboardRemove()
                )
                return

        except Exception as e:
            print(f"⚠️ Error verificando miembro nuevamente: {e}")

        # ====================================================
        # 8. CREAR ENLACE DE UNA SOLA ENTRADA
        # ====================================================

        try:

            link_temporal = bot.create_chat_invite_link(
                chat_id=ID_GRUPO,
                member_limit=1,
                name=f"YAPE-FREE-{user_id}"
            )

            bot.send_message(
                user_id,

                "🤖 <b>BOT YAPE FREE</b>\n\n"

                "✅ <b>NÚMERO VERIFICADO CORRECTAMENTE</b>\n\n"

                f"👤 <b>Nombre:</b> {nombre_completo}\n"
                f"📱 <b>Teléfono:</b> {numero}\n"
                f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"

                "💚 <b>ACCESO AL GRUPO YAPE FREE</b>\n\n"

                "Tu enlace personal está listo 👇\n\n"

                f"🔗 {link_temporal.invite_link}\n\n"

                "⚠️ <b>IMPORTANTE</b>\n"
                "• El enlace es personal.\n"
                "• Solo permite una entrada.\n"
                "• No compartas el enlace.",

                parse_mode="HTML",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )

        except Exception as e:

            print(f"❌ Error creando enlace YAPE FREE: {e}")

            bot.send_message(
                user_id,
                "🤖 <b>BOT YAPE FREE</b>\n\n"
                "❌ <b>No se pudo generar tu enlace.</b>\n\n"
                "Verifica que el bot sea administrador del grupo "
                "y tenga permiso para crear enlaces de invitación.",
                parse_mode="HTML",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )

    # ========================================================
    # 9. MENSAJE INICIAL + IMAGEN
    # ========================================================

    try:

        msg = bot.send_photo(
            chat_id=user_id,
            photo=IMAGEN_YAPE_FREE,

            caption=(
                "🤖 <b>BOT YAPE FREE</b>\n\n"

                "💚 <b>ACCESO AL GRUPO YAPE FREE</b>\n\n"

                "Para poder ingresar debes verificar primero "
                "tu número telefónico.\n\n"

                "📱 Debes compartir el número vinculado "
                "a tu propia cuenta de Telegram.\n\n"

                "🔐 Después de verificarte recibirás "
                "un enlace personal de acceso.\n\n"

                "⚠️ El enlace solamente puede utilizarse "
                "<b>una vez</b>.\n\n"

                "👇 Presiona el botón para continuar."
            ),

            parse_mode="HTML",
            reply_markup=markup
        )

    except Exception as e:

        print(f"⚠️ Error enviando imagen: {e}")

        msg = bot.send_message(
            user_id,

            "🤖 <b>BOT YAPE FREE</b>\n\n"
            "💚 <b>ACCESO AL GRUPO YAPE FREE</b>\n\n"
            "Para ingresar debes verificar tu número telefónico.\n\n"
            "👇 Presiona el botón para continuar.",

            parse_mode="HTML",
            reply_markup=markup
        )

    # ========================================================
    # 10. ESPERAR CONTACTO
    # ========================================================

    bot.register_next_step_handler(
        msg,
        procesar_contacto
    )