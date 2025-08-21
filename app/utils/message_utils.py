from aiogram.types import CallbackQuery


async def safe_edit_message(call: CallbackQuery, text: str, reply_markup=None):
    """Безопасно редактировать сообщение, учитывая наличие фото"""
    try:
        if call.message.photo:
            await call.message.edit_caption(caption=text, reply_markup=reply_markup)
        else:
            await call.message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        # Если не удалось отредактировать, отправляем новое сообщение
        try:
            if call.message.photo:
                await call.message.answer_photo(
                    call.message.photo[-1].file_id,
                    caption=text,
                    reply_markup=reply_markup
                )
            else:
                await call.message.answer(text, reply_markup=reply_markup)
        except Exception:
            # Последняя попытка - просто отправить текст
            await call.message.answer(text, reply_markup=reply_markup)