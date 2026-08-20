from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def ejecutar_grupo_vip(bot, call):
    chat_id = call.message.chat.id
    imagen_url = "https://i.postimg.cc/VN0G0Ctv/image.png"

    # Creación de la botonera (Inline Keyboard)
    markup = InlineKeyboardMarkup()
    btn_info = InlineKeyboardButton(
        text="📲 Más información aquí", 
        url="https://t.me/ReinaDark_x"  # Cambia por el link de tu perfil o canal
    )
    markup.add(btn_info)

    # Envío de la foto con el texto y la botonera
    bot.send_photo(
        chat_id,
        photo=imagen_url,
        caption=(
            "👑 <b>GRUPO VIP - ACCESO EXCLUSIVO</b>\n\n"
            "Lleva tu experiencia al siguiente nivel con un <b>único pago de por vida</b>. "
            "Sin suscripciones ni cobros mensuales.\n\n"
            "📌 <b>Beneficios:</b>\n"
            "• Contenido y productos exclusivos.\n"
            "• Atención y soporte prioritario.\n"
            "• Acceso a todas las actualizaciones.\n\n"
            "👉 Haz clic en el botón de abajo para ir directamente a nuestro perfil: @ReinaDark_x"
        ),
        parse_mode="HTML",
        reply_markup=markup
    )