# app/handlers/export.py
from aiogram import types, Router, F
from aiogram.types import BufferedInputFile, InputMediaDocument, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.utils.export_utils import export_user_debts_to_excel, get_export_filename
from app.keyboards.callbacks import CallbackData
from app.keyboards.texts import tr
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == CallbackData.EXPORT_EXCEL)
async def export_debts_callback(callback_query: types.CallbackQuery):
    """Экспорт долгов пользователя в Excel"""
    user_id = callback_query.from_user.id

    # 1. Сразу убираем "часики"
    try:
        await callback_query.answer()
    except Exception as e:
        logger.warning(f"call.answer() error for user {user_id}: {e}")

    # 2. Показываем индикатор загрузки
    try:
        loading_text = await tr(user_id, 'export_loading')
    except Exception:
        loading_text = "⏳ Подготавливаю экспорт данных..."
    try:
        await callback_query.message.edit_text(loading_text, reply_markup=None)
    except Exception as e:
        logger.warning(f"Не удалось показать индикатор загрузки: {e}")

    try:
        # 3. Генерация файла
        async with get_db() as session:  # type: AsyncSession
            excel_buffer = await export_user_debts_to_excel(session, user_id)
        filename = get_export_filename(user_id)
        file = BufferedInputFile(excel_buffer.getvalue(), filename)

        try:
            caption = await tr(user_id, 'export_success_caption')
        except Exception:
            caption = "📊 Экспорт завершен успешно!\n\n📝 Файл содержит все ваши активные долги."

        # Локализованная кнопка "Главное меню"
        try:
            back_main_text = await tr(user_id, 'back_main_btn')
        except Exception:
            back_main_text = "🏠 Главное меню"

        back_main_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=back_main_text, callback_data="back_main")]
            ]
        )

        # 4. Заменяем текущее сообщение на файл с кнопкой "Главное меню"
        await callback_query.message.edit_media(
            media=InputMediaDocument(
                media=file,
                caption=caption
            ),
            reply_markup=back_main_kb
        )

        logger.info(f"Excel export successful for user {user_id}")

    except Exception as e:
        logger.error(f"Export error for user {user_id}: {e}", exc_info=True)
        try:
            error_text = await tr(user_id, 'export_error')
        except Exception:
            error_text = f"❌ Ошибка при экспорте: {e}\n\nПопробуйте позже."

        try:
            back_main_text = await tr(user_id, 'back_main_btn')
        except Exception:
            back_main_text = "🏠 Главное меню"

        back_main_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=back_main_text, callback_data="back_main")]
            ]
        )

        try:
            await callback_query.message.edit_text(error_text, reply_markup=back_main_kb)
        except Exception as e2:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e2}")
