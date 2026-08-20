import requests
import telebot


def ejecutar_grupo_free(bot, call):
  bot.answer_callback_query(call.id)

  user_id = call.from_user.id
  ID_GRUPO = -1004286061167
  API_URL = "https://bot-apis-zkmk.vercel.app/api/contactos"

  # 1. VERIFICAR SI EL USUARIO YA ESTÁ EN EL GRUPO
  try:
    miembro = bot.get_chat_member(chat_id=ID_GRUPO, user_id=user_id)
    # Estados de usuarios activos en el grupo
    if miembro.status in ["member", "administrator", "creator"]:
      bot.send_message(
          user_id,
          "⚠️ <b>Ya eres miembro de este grupo.</b>\n\n"
          "No es necesario solicitar un nuevo enlace de acceso.",
          parse_mode="HTML",
      )
      return  # Detiene la ejecución aquí
  except Exception as e:
    # Si ocurre un error (por ejemplo, si el bot no está en el grupo), se imprime en consola
    print(f"Error al verificar estado de miembro: {e}")

  # 2. SI NO ESTÁ EN EL GRUPO, CONTINÚA EL FLUJO DE SOLICITUD DE CONTACTO
  markup = telebot.types.ReplyKeyboardMarkup(
      one_time_keyboard=True,
      resize_keyboard=True,
      input_field_placeholder="Presiona el botón de abajo 👇",
  )
  boton_contacto = telebot.types.KeyboardButton(
      text="📱 Compartir mi número telefónico", request_contact=True
  )
  markup.add(boton_contacto)

  def procesar_contacto(message):
    if message.chat.type != "private":
      return

    if message.contact:
      if message.contact.user_id != message.from_user.id:
        bot.send_message(
            user_id,
            "❌ Debes compartir **tu propio** número telefónico usando el botón.",
            reply_markup=telebot.types.ReplyKeyboardRemove(),
        )
        return

      numero = message.contact.phone_number
      nombre = message.from_user.first_name
      usuario = message.from_user.username or ""

      # Envío de datos a la API
      try:
        payload = {
            "telefono": numero,
            "nombre": nombre,
            "username": usuario,
            "chat_id": user_id,
        }
        requests.post(API_URL, json=payload, timeout=5)
      except Exception as e:
        print(f"Error guardando en la API: {e}")

      # Generación del link de un solo uso
      try:
        link_temporal = bot.create_chat_invite_link(
            chat_id=ID_GRUPO, member_limit=1
        )

        bot.send_message(
            user_id,
            f"✅ <b>Número verificado correctamente.</b>\n\n"
            f"Accede mediante tu enlace único:\n{link_temporal.invite_link}\n\n"
            f"⚠️ <i>Este enlace dejará de funcionar automáticamente en cuanto te unas.</i>",
            parse_mode="HTML",
            reply_markup=telebot.types.ReplyKeyboardRemove(),
        )
      except Exception as e:
        bot.send_message(
            user_id,
            "❌ Error: El bot debe ser **Administrador** en el grupo con permisos para crear enlaces.",
            reply_markup=telebot.types.ReplyKeyboardRemove(),
        )
    else:
      bot.send_message(
          user_id,
          "❌ Operación cancelada. Debes presionar el botón para compartir tu contacto.",
          reply_markup=telebot.types.ReplyKeyboardRemove(),
      )

  # Solicitud inicial enviada al privado
  msg = bot.send_message(
      user_id,
      "👥 <b>UNIRSE AL GRUPO FREE</b>\n\n"
      "Para obtener tu enlace de acceso, confirma tu identidad compartiendo tu número telefónico mediante el botón desplegado abajo:",
      parse_mode="HTML",
      reply_markup=markup,
  )

  bot.register_next_step_handler(msg, procesar_contacto)
