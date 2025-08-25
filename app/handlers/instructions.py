"""
Обработчики для инструкций по использованию бота
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.keyboards import tr
from app.utils import safe_edit_message

router = Router()


@router.callback_query(F.data == 'how_to_use')
async def show_instructions(call: CallbackQuery, state: FSMContext):
    """Показать инструкции по использованию"""
    user_id = call.from_user.id

    # Получаем язык пользователя для выбора ссылки
    from app.database import get_user_data
    try:
        user_data = await get_user_data(user_id)
        lang = user_data.get('lang', 'uz')  # По умолчанию узбекский
    except:
        lang = 'uz'

    instruction_text_ru = """
📖 **Как пользоваться ботом:**

1️⃣ **Добавить долг** - создать запись о долге
   • Укажите имя человека
   • Выберите валюту (USD, UZS, EUR)  
   • Введите сумму
   • Укажите дату возврата
   • Выберите направление (дал/взял)
   • Добавьте комментарий (необязательно)

2️⃣ **Мои долги** - посмотреть все долги
   • Список всех активных долгов
   • Нажмите на долг для просмотра деталей
   • Можно редактировать, закрывать или удалять

3️⃣ **Настройки** - управление уведомлениями
   • Установить время напоминаний
   • Бот будет присылать уведомления о долгах

4️⃣ **Очистить все** - удалить все долги

5️⃣ **Смена языка** - переключение между языками

❓ Если возникли вопросы, попробуйте добавить тестовый долг и поэкспериментировать с функциями бота.
"""

    instruction_text_uz = """
📖 **Botdan qanday foydalanish:**

1️⃣ **Qarz qo'shish** - qarz haqida yozuv yaratish
   • Shaxsning ismini kiriting
   • Valyutani tanlang (USD, UZS, EUR)
   • Summani kiriting
   • Qaytarish sanasini belgilang
   • Yo'nalishni tanlang (berdingiz/oldingiz)
   • Izoh qo'shing (ixtiyoriy)

2️⃣ **Qarzlarim** - barcha qarzlarni ko'rish
   • Barcha faol qarzlar ro'yxati
   • Tafsilotlar uchun qarzga bosing
   • Tahrirlash, yopish yoki o'chirish mumkin

3️⃣ **Sozlamalar** - bildirishnomalarni boshqarish
   • Eslatma vaqtini belgilang
   • Bot qarzlar haqida bildirishnoma yuboradi

4️⃣ **Hammasini o'chirish** - barcha qarzlarni o'chirish

5️⃣ **Tilni o'zgartirish** - tillar o'rtasida almashtirish

❓ Savollar bo'lsa, sinov qarzini qo'shib, bot funktsiyalarini sinab ko'ring.
"""

    # Выбираем текст и ссылку в зависимости от языка
    if lang == 'ru':
        instruction_text = instruction_text_ru
        telegraph_url = "https://telegra.ph/QarzNazoratBot--Instrukciya-polzovatelya-07-16"
        link_text = "📖 Подробная инструкция"
    else:
        instruction_text = instruction_text_uz
        telegraph_url = "https://telegra.ph/QarzNazoratBot--Foydalanuvchi-uchun-yoriqnoma-07-16"
        link_text = "📖 Batafsil yo'riqnoma"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=link_text,
            url=telegraph_url
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )]
    ])

    await safe_edit_message(call, instruction_text, kb, parse_mode='Markdown')