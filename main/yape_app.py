from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def ejecutar_yape_app(bot, call):
    chat_id = call.message.chat.id
    imagen_url = "https://i.postimg.cc/R0YhtDCr/image.png"

    # Creación del botón con enlace
    markup = InlineKeyboardMarkup()
    boton_descarga = InlineKeyboardButton(
        text="📲 Descargar Yape APK Gratis", 
        url="https://ypfk-plus.vercel.app/"
    )
    markup.add(boton_descarga)

    # Mensaje con foto y botonera
    bot.send_photo(
        chat_id,
        imagen_url,
        caption=(
            "📱 <b>YAPE APP - DESCARGA OFICIAL</b>\n\n"
            "Obtén la aplicación original totalmente gratis para transferir dinero, "
            "pagar servicios y realizar recargas de forma 100% segura.\n\n"
            "👉 Haz clic en el botón de abajo para ir a la descarga oficial:"
        ),
        parse_mode="HTML",
        reply_markup=markup
    )