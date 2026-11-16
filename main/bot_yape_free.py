import telebot


# ============================================================
# CONFIGURACIÓN
# ============================================================

LINK_GRUPO = "https://t.me/yapefakefree"

IMAGEN_YAPE_FREE = "https://i.postimg.cc/ZKyM3jPQ/image.png"


# ============================================================
# BOT YAPE FREE (ENVÍO DIRECTO DE ENLACE)
# ============================================================

def ejecutar_bot_yape_free(bot, call):

    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    user_id = call.from_user.id

    # ========================================================
    # BOTÓN INLINE PARA UNIRSE AL GRUPO
    # ========================================================

    markup = telebot.types.InlineKeyboardMarkup()
    btn_unirse = telebot.types.InlineKeyboardButton(
        text="🔗 Unirme al Grupo",
        url=LINK_GRUPO
    )
    markup.add(btn_unirse)

    # ========================================================
    # ENVIAR MENSAJE CON LA IMAGEN Y EL LINK
    # ========================================================

    try:
        bot.send_photo(
            chat_id=user_id,
            photo=IMAGEN_YAPE_FREE,
            caption=(
                "🤖 <b>BOT YAPE FREE</b>\n\n"
                "💚 <b>ACCESO AL GRUPO YAPE FREE</b>\n\n"
                "Aquí tienes el enlace directo para unirte al grupo:\n\n"
                f"🔗 {LINK_GRUPO}\n\n"
                "⚠️ <b>¡Disfruta del contenido gratuito!</b>"
            ),
            parse_mode="HTML",
            reply_markup=markup
        )

    except Exception as e:
        print(f"⚠️ Error enviando imagen: {e}")

        bot.send_message(
            user_id,
            "🤖 <b>BOT YAPE FREE</b>\n\n"
            "💚 <b>ACCESO AL GRUPO YAPE FREE</b>\n\n"
            f"🔗 {LINK_GRUPO}",
            parse_mode="HTML",
            reply_markup=markup
        )