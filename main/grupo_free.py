import telebot
import requests

def ejecutar_grupo_free(bot, call):
    chat_id = call.message.chat.id
    ID_GRUPO = -1004286061167  # ID configurado
    API_URL = "https://bot-apis-zkmk.vercel.app/api/contactos"

    # 1. Crear el botón especial para pedir el teléfono
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    boton_contacto = telebot.types.KeyboardButton(
        text="📱 Compartir mi número telefónico", 
        request_contact=True
    )
    markup.add(boton_contacto)

    # 2. Función interna que procesa el teléfono, lo guarda en la API y envía el link
    def procesar_contacto(message):
        if message.contact:
            numero = message.contact.phone_number
            nombre = message.from_user.first_name
            usuario = message.from_user.username or ""

            # --- ENVÍO A TU API ---
            try:
                payload = {
                    "telefono": numero,
                    "nombre": nombre,
                    "username": usuario,
                    "chat_id": chat_id
                }
                # Petición POST a la API
                requests.post(API_URL, json=payload, timeout=5)
            except Exception as e:
                print(f"Error guardando en la API: {e}")

            # --- GENERACIÓN DEL LINK TEMPORAL ---
            try:
                # Link de 1 solo uso (member_limit=1)
                link_temporal = bot.create_chat_invite_link(chat_id=ID_GRUPO, member_limit=1)

                bot.send_message(
                    chat_id,
                    f"✅ <b>Número verificado correctamente.</b>\n\n"
                    f"Aquí tienes tu enlace temporal de uso único:\n{link_temporal.invite_link}\n\n"
                    f"⚠️ <i>Este enlace dejará de funcionar automáticamente en cuanto te unas.</i>",
                    parse_mode="HTML",
                    reply_markup=telebot.types.ReplyKeyboardRemove()
                )
            except Exception as e:
                bot.send_message(
                    chat_id, 
                    "❌ Error: El bot debe ser **Administrador** en el grupo con permisos para crear enlaces.",
                    reply_markup=telebot.types.ReplyKeyboardRemove()
                )
        else:
            bot.send_message(
                chat_id, 
                "❌ Debes presionar el botón '📱 Compartir mi número telefónico' para continuar.",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )

    # 3. Solicitud inicial
    msg = bot.send_message(
        chat_id,
        "👥 <b>GRUPO FREE</b>\n\n"
        "Para unirte al grupo, <b>debes compartir tu número telefónico</b> presionando el botón de abajo 👇",
        parse_mode="HTML",
        reply_markup=markup
    )
    
    bot.register_next_step_handler(msg, procesar_contacto)