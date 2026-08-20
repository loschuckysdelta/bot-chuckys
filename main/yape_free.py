from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def ejecutar_yape_free(bot, call):
    chat_id = call.message.chat.id
    imagen_url = "https://i.postimg.cc/CxC4hk6t/image.png"

    # Creación de la botonera
    markup = InlineKeyboardMarkup()
    btn_link = InlineKeyboardButton(text="📲 YAPE BETA GRATIS ", url="https://loschuckys.com/yape")
    markup.add(btn_link)

    # Texto con el formato solicitado
    caption_text = (
        "💚 <b>YAPE FREE</b>\n\n"
        "Obténlo completamente gratis acá abajo en la opción beta."
    )

    bot.send_photo(
        chat_id,
        photo=imagen_url,
        caption=caption_text,
        parse_mode="HTML",
        reply_markup=markup
    )