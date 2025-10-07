"""
Сервис для получения курсов валют из внешнего API
"""
import asyncio
import aiohttp
from typing import Dict, Optional
from datetime import datetime, timedelta
import json
from app.keyboards import tr
# Кэш для хранения курсов валют
_currency_cache = {}
_cache_expires = None
CACHE_DURATION = 300  # 5 минут


class CurrencyService:
    """Сервис для работы с курсами валют"""

    # Используем бесплатный API
    BASE_URL = "https://api.exchangerate-api.com/v4/latest/USD"

    @staticmethod
    async def get_exchange_rates() -> Optional[Dict[str, float]]:
        """
        Получить актуальные курсы валют относительно UZS
        Возвращает словарь вида: {"USD": 12000.0, "EUR": 11000.0, "RUB": 165.0}
        """
        global _currency_cache, _cache_expires

        # Проверяем кэш
        if _cache_expires and datetime.now() < _cache_expires and _currency_cache:
            print("✅ Используем кэшированные курсы валют")
            return _currency_cache.copy()

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(10)) as session:
                print("🌐 Запрашиваем актуальные курсы валют...")

                async with session.get(CurrencyService.BASE_URL) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Получаем курсы относительно USD
                        usd_rates = data.get("rates", {})
                        uzs_per_usd = usd_rates.get("UZS", 12450.0)
                        eur_per_usd = usd_rates.get("EUR", 0.85)
                        rub_per_usd = usd_rates.get("RUB", 90.0)

                        # Конвертируем все в UZS (сколько UZS за 1 единицу валюты)
                        rates = {
                            "UZS": 1.0,  # базовая валюта
                            "USD": round(uzs_per_usd, 2),  # сколько UZS за 1 USD
                            "EUR": round(uzs_per_usd / eur_per_usd, 2),  # сколько UZS за 1 EUR
                            "RUB": round(uzs_per_usd / rub_per_usd, 2)  # сколько UZS за 1 RUB
                        }

                        # Сохраняем в кэш
                        _currency_cache = rates
                        _cache_expires = datetime.now() + timedelta(seconds=CACHE_DURATION)

                        print(f"✅ Курсы обновлены: USD={rates['USD']}, EUR={rates['EUR']}, RUB={rates['RUB']} UZS")
                        return rates

                    else:
                        print(f"❌ Ошибка API: статус {response.status}")
                        return CurrencyService._get_fallback_rates()

        except asyncio.TimeoutError:
            print("⏰ Таймаут при запросе курсов валют")
            return CurrencyService._get_fallback_rates()

        except aiohttp.ClientError as e:
            print(f"🌐 Сетевая ошибка при получении курсов: {e}")
            return CurrencyService._get_fallback_rates()

        except Exception as e:
            print(f"❌ Неожиданная ошибка при получении курсов: {e}")
            return CurrencyService._get_fallback_rates()

    @staticmethod
    def _get_fallback_rates() -> Dict[str, float]:
        """Резервные курсы валют на случай недоступности API"""
        fallback_rates = {
            "UZS": 1.0,
            "USD": 12000.0,
            "EUR": 11000.0,
            "RUB": 165.0
        }

        print("⚠️ Используем резервные курсы валют")

        # Сохраняем в кэш резервные значения на короткое время
        global _currency_cache, _cache_expires
        _currency_cache = fallback_rates
        _cache_expires = datetime.now() + timedelta(seconds=60)  # Кэшируем на 1 минуту

        return fallback_rates

    @staticmethod
    async def format_currency_message(user_id: int, tr_func) -> str:
        """
        Форматирует сообщение с курсами валют для отправки пользователю
        """
        try:
            rates = await CurrencyService.get_exchange_rates()

            if not rates:
                return await tr_func(user_id, 'currency_error')

            # Форматируем красивое сообщение
            message_parts = [f"{await tr(user_id, 'currency_rates')}:"]

            # USD к UZS
            if "USD" in rates:
                usd_rate = rates["USD"]
                message_parts.append(f"🇺🇸 USD: {usd_rate:.0f} UZS")

            # EUR к UZS
            if "EUR" in rates:
                eur_rate = rates["EUR"]
                message_parts.append(f"🇪🇺 EUR: {eur_rate:.0f} UZS")

            # RUB к UZS
            if "RUB" in rates:
                rub_rate = rates["RUB"]
                message_parts.append(f"🇷🇺 RUB: {rub_rate:.0f} UZS")

            # Добавляем время обновления
            current_time = datetime.now().strftime("%H:%M")
            message_parts.append(f"\n{await tr(user_id, 'updated')} {current_time}")

            return "\n".join(message_parts)

        except Exception as e:
            print(f"❌ Ошибка форматирования сообщения о курсах: {e}")
            return await tr_func(user_id, 'currency_format_error')

    @staticmethod
    async def convert_currency(amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Конвертировать сумму из одной валюты в другую
        """
        try:
            rates = await CurrencyService.get_exchange_rates()

            if not rates or from_currency not in rates or to_currency not in rates:
                return None

            # Конвертируем через UZS как базовую валюту
            uzs_amount = amount * rates[from_currency]
            result = uzs_amount / rates[to_currency]

            return round(result, 2)

        except Exception as e:
            print(f"❌ Ошибка конвертации валют: {e}")
            return None

    @staticmethod
    def clear_cache():
        """Очистить кэш курсов валют"""
        global _currency_cache, _cache_expires
        _currency_cache = {}
        _cache_expires = None
        print("🗑️ Кэш курсов валют очищен")


# Вспомогательные функции для использования в других частях приложения

async def get_currency_rates() -> Optional[Dict[str, float]]:
    """Получить актуальные курсы валют (короткий алиас)"""
    return await CurrencyService.get_exchange_rates()


async def format_currency_notification(user_id: int, tr_func) -> str:
    """Форматировать уведомление о курсах валют"""
    return await CurrencyService.format_currency_message(user_id, tr_func)


async def convert_amount(amount: float, from_curr: str, to_curr: str) -> Optional[float]:
    """Конвертировать сумму между валютами (короткий алиас)"""
    return await CurrencyService.convert_currency(amount, from_curr, to_curr)


async def convert_currency(direction: str, amount: float):
    """
    Конвертировать сумму по направлению вида 'uzs_usd', 'usd_eur' и т.д.
    Совместимость со старыми вызовами.
    """
    try:
        from_curr, to_curr = direction.split("_")
        return await CurrencyService.convert_currency(amount, from_curr.upper(), to_curr.upper())
    except Exception as e:
        print(f"❌ Ошибка в convert_currency: {e}")
        return None