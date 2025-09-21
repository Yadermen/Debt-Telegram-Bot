"""
Сервис для получения курсов валют из внешнего API
"""
import asyncio
import aiohttp
from typing import Dict, Optional
from datetime import datetime, timedelta
import json

# Кэш для хранения курсов валют
_currency_cache = {}
_cache_expires = None
CACHE_DURATION = 300  # 5 минут


class CurrencyService:
    """Сервис для работы с курсами валют"""

    # Используем бесплатный API (или можно заменить на другой)
    BASE_URL = "https://api.exchangerate-api.com/v4/latest/USD"

    # Альтернативы:
    # "https://open.er-api.com/v6/latest/USD"
    # "https://api.fxratesapi.com/latest?base=USD"

    @staticmethod
    async def get_exchange_rates() -> Optional[Dict[str, float]]:
        """
        Получить актуальные курсы валют
        Возвращает словарь вида: {"USD": 1.0, "EUR": 0.85, "UZS": 12450.0}
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

                        # Извлекаем нужные нам курсы
                        rates = {
                            "USD": 1.0,  # базовая валюта
                            "EUR": data.get("rates", {}).get("EUR", 0.85),
                            "UZS": data.get("rates", {}).get("UZS", 12450.0)
                        }

                        # Сохраняем в кэш
                        _currency_cache = rates
                        _cache_expires = datetime.now() + timedelta(seconds=CACHE_DURATION)

                        print(f"✅ Курсы обновлены: USD=1, EUR={rates['EUR']}, UZS={rates['UZS']}")
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
            "USD": 1.0,
            "EUR": 0.85,
            "UZS": 12450.0
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
            message_parts = ["💱 Актуальные курсы валют:"]

            # USD всегда 1.0 (базовая валюта)
            message_parts.append(f"🇺🇸 USD: 1.00")

            # EUR к USD
            if "EUR" in rates:
                eur_rate = rates["EUR"]
                message_parts.append(f"🇪🇺 EUR: {eur_rate:.4f}")

            # UZS к USD
            if "UZS" in rates:
                uzs_rate = rates["UZS"]
                message_parts.append(f"🇺🇿 UZS: {uzs_rate:.2f}")

            # Добавляем время обновления
            current_time = datetime.now().strftime("%H:%M")
            message_parts.append(f"\n🕐 Обновлено: {current_time}")

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

            # Конвертируем через USD как базовую валюту
            usd_amount = amount / rates[from_currency]
            result = usd_amount * rates[to_currency]

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