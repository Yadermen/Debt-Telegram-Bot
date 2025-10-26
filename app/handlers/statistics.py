"""
Модуль для работы со статистикой долгов
Включает сервис, клавиатуры и обработчики
"""
from typing import Dict, Optional
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from app.database.crud import get_open_debts, get_user_data
from app.keyboards import CallbackData
from app.utils.currency_api import CurrencyService
from app.keyboards.texts import tr
from app.utils import safe_edit_message

# Создаем роутер для статистики
router = Router()

# Словарь месяцев на русском
MONTHS_RU = {
    1: "январь", 2: "февраль", 3: "март", 4: "апрель",
    5: "май", 6: "июнь", 7: "июль", 8: "август",
    9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь"
}

# Словарь месяцев на узбекском
MONTHS_UZ = {
    1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel",
    5: "may", 6: "iyun", 7: "iyul", 8: "avgust",
    9: "sentabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"
}


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def get_month_name(month: int, lang: str) -> str:
    """Получить название месяца на нужном языке"""
    if lang == "uz":
        return MONTHS_UZ.get(month, str(month))
    return MONTHS_RU.get(month, str(month))


# ==================== КЛАВИАТУРЫ ====================

async def get_statistics_keyboard(user_id: int, current_currency: str = "USD") -> InlineKeyboardMarkup:
    """
    Клавиатура для статистики с кнопками выбора валюты и экспорта
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇸 USD", callback_data="stats_currency_USD"),
            InlineKeyboardButton(text="🇪🇺 EUR", callback_data="stats_currency_EUR"),
            InlineKeyboardButton(text="🇺🇿 UZS", callback_data="stats_currency_UZS")
        ],
        [
            InlineKeyboardButton(
                text=f"{await tr(user_id, 'statistics_btn_export')}",
                callback_data=CallbackData.EXPORT_EXCEL
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{await tr(user_id, 'statistics_btn_back')}",
                callback_data=CallbackData.BACK_MAIN
            )
        ]
    ])

    return keyboard


# ==================== СЕРВИС СТАТИСТИКИ ====================

class StatisticsService:
    """Сервис для расчета и форматирования статистики долгов"""

    @staticmethod
    async def calculate_statistics(user_id: int, target_currency: str = "USD") -> Optional[Dict]:
        """
        Вычислить статистику долгов пользователя в выбранной валюте

        Args:
            user_id: ID пользователя
            target_currency: Валюта для отображения (USD, EUR, UZS)

        Returns:
            Словарь со статистикой или None в случае ошибки
        """
        try:
            from app.database.connection import get_db
            from app.database.models import Debt
            from sqlalchemy import select, func, and_

            # Получаем ВСЕ активные долги пользователя (и открытые и закрытые)
            async with get_db() as session:
                result = await session.execute(
                    select(Debt).where(
                        and_(
                            Debt.user_id == user_id,
                            Debt.is_active.is_(True)
                        )
                    ).order_by(Debt.id)
                )
                debt_rows = result.scalars().all()

                debts = []
                for debt in debt_rows:
                    debts.append({
                        'id': debt.id,
                        'amount': debt.amount,
                        'currency': debt.currency,
                        'direction': debt.direction,
                        'date': debt.date,
                        'closed': debt.closed
                    })

            # Получаем курсы валют
            rates = await CurrencyService.get_exchange_rates()
            if not rates:
                print("❌ Не удалось получить курсы валют для статистики")
                return None

            # Инициализируем счетчики
            total_owe = 0.0  # Сколько должен я (direction='owe')
            total_owed = 0.0  # Сколько должны мне (direction='owed')
            open_count = 0

            # Текущий месяц для подсчета закрытых долгов
            now = datetime.now()

            for debt in debts:
                amount = debt['amount']
                currency = debt.get('currency', 'UZS')
                direction = debt['direction']
                closed = debt.get('closed', False)

                # Конвертируем сумму в целевую валюту
                converted_amount = await StatisticsService._convert_to_target(
                    amount, currency, target_currency, rates
                )

                if converted_amount is None:
                    continue

                # Считаем только открытые долги (closed=False)
                if not closed:
                    if direction == 'owe':
                        # Я должен
                        total_owe += converted_amount
                        open_count += 1
                    elif direction == 'owed':
                        # Мне должны
                        total_owed += converted_amount
                        open_count += 1

            # Считаем закрытые долги за месяц (closed=True и date в текущем месяце)
            current_month_str = now.strftime('%Y-%m')
            async with get_db() as session:
                result_closed = await session.execute(
                    select(func.count(Debt.id)).where(
                        and_(
                            Debt.user_id == user_id,
                            Debt.is_active.is_(True),
                            Debt.closed.is_(True),
                            Debt.date.like(f"{current_month_str}%")
                        )
                    )
                )
                closed_this_month = result_closed.scalar() or 0

            # Рассчитываем разницу (положительная = мне должны больше)
            difference = total_owed - total_owe
            sign = "+" if difference >= 0 else ""

            return {
                'total_owe': round(total_owe, 2),
                'total_owed': round(total_owed, 2),
                'difference': round(difference, 2),
                'sign': sign,
                'closed_count': closed_this_month,
                'remaining_count': open_count,
                'currency': target_currency,
                'month': now.month
            }

        except Exception as e:
            print(f"❌ Ошибка при расчете статистики: {e}")
            return None

    @staticmethod
    async def _convert_to_target(amount: float, from_currency: str,
                                 to_currency: str, rates: Dict) -> Optional[float]:
        """
        Конвертировать сумму из одной валюты в другую через UZS

        Args:
            amount: Сумма для конвертации
            from_currency: Исходная валюта
            to_currency: Целевая валюта
            rates: Словарь с курсами валют

        Returns:
            Сконвертированная сумма или None
        """
        try:
            if from_currency == to_currency:
                return amount

            if from_currency not in rates or to_currency not in rates:
                print(f"⚠️ Валюта {from_currency} или {to_currency} не найдена в курсах")
                return None

            # Конвертируем через UZS как базовую валюту
            # Сначала переводим в UZS
            uzs_amount = amount * rates[from_currency]

            # Затем из UZS в целевую валюту
            result = uzs_amount / rates[to_currency]

            return result

        except Exception as e:
            print(f"❌ Ошибка конвертации {from_currency} -> {to_currency}: {e}")
            return None

    @staticmethod
    async def format_statistics_message(user_id: int, target_currency: str = "USD") -> str:
        """
        Форматировать красивое сообщение со статистикой

        Args:
            user_id: ID пользователя
            target_currency: Валюта для отображения

        Returns:
            Отформатированное сообщение
        """
        try:
            # Получаем язык пользователя
            user_data = await get_user_data(user_id)
            lang = user_data.get('lang', 'ru')

            # Получаем статистику
            stats = await StatisticsService.calculate_statistics(user_id, target_currency)

            if not stats:
                return await tr(user_id, 'statistics_error')

            # Получаем символ валюты
            currency_symbols = {
                'USD': '$',
                'EUR': '€',
                'UZS': 'UZS'
            }
            symbol = currency_symbols.get(target_currency, target_currency)

            # Получаем название месяца
            month_name = await get_month_name(stats['month'], lang)

            # Форматируем суммы
            if target_currency == 'UZS':
                owe_str = f"{stats['total_owe']:,.0f} {symbol}"
                owed_str = f"{stats['total_owed']:,.0f} {symbol}"
                diff_str = f"{stats['sign']}{abs(stats['difference']):,.0f} {symbol}"
            else:
                owe_str = f"{symbol}{stats['total_owe']:,.2f}"
                owed_str = f"{symbol}{stats['total_owed']:,.2f}"
                diff_str = f"{stats['sign']}{symbol}{abs(stats['difference']):,.2f}"

            # Формируем сообщение
            message = f"""📊 {await tr(user_id, 'statistics_title')}

 {await tr(user_id, 'statistics_debts')}: {owe_str}
 {await tr(user_id, 'statistics_loans')}: {owed_str}
 {await tr(user_id, 'statistics_difference')}: {diff_str}

 {await tr(user_id, 'statistics_month', month=month_name)}:
 {await tr(user_id, 'statistics_closed')}: {stats['closed_count']}
 {await tr(user_id, 'statistics_remaining')}: {stats['remaining_count']}

 {await tr(user_id, 'statistics_currency')}: {target_currency}"""

            return message

        except Exception as e:
            print(f"❌ Ошибка форматирования статистики: {e}")
            return await tr(user_id, 'statistics_format_error')


# ==================== ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == CallbackData.STATISTICS)
async def show_statistics(callback: CallbackQuery):
    """
    Показать статистику пользователя
    """
    user_id = callback.from_user.id

    # По умолчанию показываем в USD
    stats_text = await StatisticsService.format_statistics_message(user_id, "USD")
    keyboard = await get_statistics_keyboard(user_id, current_currency="USD")

    await safe_edit_message(
        callback,
        stats_text,
        reply_markup=keyboard
    )

    await callback.answer()


@router.callback_query(F.data.startswith("stats_currency_"))
async def callback_change_currency(callback: CallbackQuery):
    """
    Обработчик переключения валюты в статистике
    Формат callback_data: stats_currency_USD / stats_currency_EUR / stats_currency_UZS
    """
    user_id = callback.from_user.id

    # Извлекаем валюту из callback_data
    currency = callback.data.split("_")[-1]  # USD, EUR или UZS

    # Проверяем, не изменилась ли валюта (защита от двойного клика)
    current_text = callback.message.text
    if f"🌍 Валюта: {currency}" in current_text or f"Валюта: {currency}" in current_text:
        await callback.answer()
        return

    # Форматируем сообщение с новой валютой
    stats_text = await StatisticsService.format_statistics_message(user_id, currency)
    keyboard = await get_statistics_keyboard(user_id, current_currency=currency)

    # Обновляем сообщение
    await safe_edit_message(
        callback,
        stats_text,
        reply_markup=keyboard
    )

    await callback.answer()

@router.callback_query(F.data == "stats_export_excel")
async def callback_export_excel(callback: CallbackQuery):
    """
    Обработчик экспорта в Excel
    ЗДЕСЬ ПОДКЛЮЧИШЬ СВОЮ ЛОГИКУ ЭКСПОРТА
    """
    user_id = callback.from_user.id
    await callback.answer(
        await tr(user_id, "statistics_export_placeholder"),
        show_alert=True
    )

    # Твой код экспорта будет примерно таким:
    # excel_file = await generate_excel_report(user_id)
    # await callback.message.answer_document(excel_file)





# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ИСПОЛЬЗОВАНИЯ В ДРУГИХ МОДУЛЯХ ====================

async def get_statistics(user_id: int, currency: str = "USD") -> Optional[Dict]:
    """Получить статистику (короткий алиас)"""
    return await StatisticsService.calculate_statistics(user_id, currency)


async def format_stats_message(user_id: int, currency: str = "USD") -> str:
    """Форматировать сообщение со статистикой (короткий алиас)"""
    return await StatisticsService.format_statistics_message(user_id, currency)