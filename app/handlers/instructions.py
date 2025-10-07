"""
Обработчики для инструкций по использованию бота - исправленная версия с полной обработкой ошибок
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

try:
    from app.keyboards import tr
    from app.utils import safe_edit_message
except ImportError as e:
    print(f"❌ Ошибка импорта в instructions.py: {e}")

router = Router()


@router.callback_query(F.data == 'how_to_use')
async def show_instructions(call: CallbackQuery, state: FSMContext):
    """Показать инструкции по использованию"""
    user_id = call.from_user.id

    try:
        await state.clear()

        # Получаем язык пользователя для выбора ссылки
        try:
            from app.database import get_user_data
            user_data = await get_user_data(user_id)
            lang = user_data.get('lang', 'uz')  # По умолчанию узбекский
        except Exception as db_e:
            print(f"❌ Ошибка получения данных пользователя: {db_e}")
            lang = 'uz'

        instruction_text_ru = """
Главное меню

➕ Добавить долг – добавить новый долг:

Обычный: пошаговое добавление
• Имя человека
• Валюта (USD, UZS, EUR)
• Сумма
• Дата возврата
• Направление (я должен / мне должны)
• Комментарий (необязательно)

Через ИИ: введите данные одним текстом:
направление, контрагент, сумма и валюта, срок, описание (необязательно)
Пример: я должен Али 250 USD 2025-10-05 за обед

📋 Мои долги – список всех долгов:

Каждая запись ведёт к карточке долга
В карточке можно: погасить, изменить, продлить или удалить долг

📊 Экспорт в Excel – выгрузка всех долгов
🧹 Очистить всё – удалить все долги
⬅️ Назад – возврат в главное меню

🔔 Напоминания – управление уведомлениями:
Добавить новое напоминание с датой и повторением
Включить/выключить напоминания для долгов
Настроить время уведомлений
Установка автоматических уведомлений:
⏰ Включить курс валют утром (7:00)
⏰ Включить курс валют вечером (17:00)
❌ Выключить курс валют

💱 Курс валют – просмотр и конвертация валют:
Сум, USD, EUR, RUB и др.

⚙️ Настройки – смена языка и общие настройки бота

ℹ️ Помощь – краткая инструкция по использованию бота

💡 Совет: попробуйте сначала добавить тестовый долг, чтобы понять, как работают все функции.

📣 Следите за новостями и обновлениями бота в нашем канале: @QarzNazorat
"""

        instruction_text_uz = """
Asosiy menyu

➕ Qarzni qo‘shish – yangi qarz qo‘shish:

Oddiy: bosqichma-bosqich qo‘shish
• Shaxs ismi
• Valyuta (USD, UZS, EUR)
• Miqdor
• Qaytarish sanasi
• Yo‘nalish (men qarzdorman / menga qarzdor)
• Izoh (majburiy emas)

AI orqali: barcha ma’lumotni bitta matnda kiriting:
yo‘nalish, kontragent, miqdor va valyuta, muddat, izoh (majburiy emas)
Misol: men qarzdorman Ali 250 USD 2025-10-05 tushlik uchun

📋 Mening qarzlarim – barcha qarzlar ro‘yxati:
Har bir yozuv qarz kartasiga olib boradi
Qarz tafsilotlari: to‘lash, o‘zgartirish, uzaytirish yoki o‘chirish mumkin

📊 Excel-ga eksport – barcha qarzlarni eksport qilish
🧹 Hammasini tozalash – barcha qarzlarni o‘chirish
⬅️ Orqaga – asosiy menyuga qaytish

🔔 Eslatmalar – bildirishnomalarni boshqarish:
Yangi eslatma qo‘shish (sana va takrorlash bilan)
Qarzlar uchun eslatmalarni yoqish/o‘chirish
Bildirish vaqti sozlash
Avtomatik bildirishnomalarni sozlash:
⏰ Valyuta kursini ertalab yoqish (7:00)
⏰ Valyuta kursini kechqurun yoqish (17:00)
❌ Valyuta kursini o‘chirish

💱 Valyuta kursi – valyutalarni ko‘rish va konvertatsiya:
UZS, USD, EUR, RUB va boshqalar

⚙️ Sozlamalar – tilni o‘zgartirish va bot sozlamalari

ℹ️ Yordam – botdan foydalanish bo‘yicha qisqacha ko‘rsatma

💡 Maslahat: avval test qarz qo‘shib ko‘ring, shunda barcha funksiyalarni tushunasiz.

📣 Bot yangiliklari va yangilanishlarini kanalimizdan kuzatib boring: @QarzNazorat
"""

        # Выбираем текст и ссылку в зависимости от языка
        try:
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

        except Exception as ui_e:
            print(f"❌ Ошибка формирования UI инструкций: {ui_e}")
            try:
                # Базовая инструкция без форматирования
                basic_text = "📖 Инструкция по использованию бота\n\nДобавляйте долги, просматривайте список, настраивайте напоминания."
                basic_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="В меню", callback_data='back_main')]
                ])
                await safe_edit_message(call, basic_text, basic_kb)
            except Exception as basic_e:
                print(f"❌ Ошибка базовой инструкции: {basic_e}")
                try:
                    await call.answer("❌ Ошибка загрузки инструкций")
                except:
                    pass

    except Exception as e:
        print(f"❌ Критическая ошибка в show_instructions: {e}")
        try:
            await call.answer("❌ Ошибка инструкций")
        except:
            pass