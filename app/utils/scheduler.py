"""
Планировщик напоминаний
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import asyncio
import traceback
import calendar
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from app.database.models import Reminder
from app.database.crud import (
    get_due_reminders,
    get_due_repeating_reminders,
    update_reminder_due,
    delete_reminder
)
from app.keyboards import main_menu


class ReminderScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.bot = None
        self.started = False
        self.running = False
        print("🔧 ReminderScheduler инициализирован")

    def set_bot(self, bot):
        """Установить экземпляр бота"""
        self.bot = bot
        print(f"🤖 Бот установлен в scheduler: {bot is not None}")

    async def start(self):
        """Запустить планировщик"""
        if not self.started:
            self.scheduler.start()
            self.started = True
            self.running = True
            print("✅ Планировщик напоминаний запущен")
        else:
            print("⚠️ Планировщик уже запущен")

    async def stop(self):
        """Остановить планировщик"""
        if self.started:
            self.scheduler.shutdown()
            self.started = False
            self.running = False
            print("🔴 Планировщик напоминаний остановлен")

    async def send_due_reminders(self):
        """Отправить напоминания о просроченных долгах"""
        print("\n" + "="*50)
        print("📅 ЗАПУСК: send_due_reminders")
        print("="*50)

        if not self.bot:
            print("❌ Bot не установлен в scheduler")
            return

        try:
            from app.database import get_due_debts_for_reminders, get_user_data
            from app.keyboards import tr, safe_str

            today = datetime.now().strftime('%Y-%m-%d')
            print(f"📆 Текущая дата: {today}")

            due_debts = await get_due_debts_for_reminders(today)
            print(f"📋 Получено долгов из БД: {len(due_debts)}")

            if not due_debts:
                print("✅ Просроченных долгов нет")
                return

            # Группируем долги по пользователям
            user_debts = {}
            for debt in due_debts:
                user_id = debt['user_id']
                if user_id not in user_debts:
                    user_debts[user_id] = []
                user_debts[user_id].append(debt)

            print(f"👥 Пользователей с долгами: {len(user_debts)}")

            # Отправляем напоминания каждому пользователю
            for user_id, debts in user_debts.items():
                try:
                    print(f"📤 Отправка напоминания пользователю {user_id} ({len(debts)} долгов)")
                    await self._send_user_reminder(user_id, debts)
                    print(f"✅ Напоминание отправлено пользователю {user_id}")
                except Exception as e:
                    print(f"❌ Ошибка отправки напоминания пользователю {user_id}: {e}")
                    traceback.print_exc()

        except Exception as e:
            print(f"❌ Критическая ошибка в send_due_reminders: {e}")
            traceback.print_exc()
        finally:
            print("="*50 + "\n")

    async def send_daily_reminders(self, user_id: int):
        """Отправить ежедневные напоминания конкретному пользователю"""
        print("\n" + "="*50)
        print(f"📅 ЗАПУСК: send_daily_reminders для user_id={user_id}")
        print("="*50)

        if not self.bot:
            print("❌ Bot не установлен в scheduler")
            return

        try:
            from app.database import get_open_debts
            from app.keyboards import tr, safe_str

            debts = await get_open_debts(user_id)
            print(f"📋 Получено открытых долгов: {len(debts)}")

            if not debts:
                print("ℹ️ У пользователя нет открытых долгов")
                return

            today = datetime.now().date()
            upcoming_debts = []

            for debt in debts:
                try:
                    due_date = datetime.strptime(debt['due'], '%Y-%m-%d').date()
                    days_left = (due_date - today).days

                    if days_left <= 3:
                        upcoming_debts.append((debt, days_left))
                        print(f"  ⏰ Долг '{debt['person']}': осталось {days_left} дней")
                except Exception as e:
                    print(f"  ⚠️ Ошибка обработки долга: {e}")
                    continue

            print(f"📊 Долгов требующих напоминания: {len(upcoming_debts)}")

            if not upcoming_debts:
                print("ℹ️ Нет долгов требующих напоминания")
                return

            # Формируем сообщение
            message_lines = [await tr(user_id, 'daily_reminder_header')]

            for debt, days_left in upcoming_debts:
                direction = debt.get('direction', 'owed')

                if days_left < 0:
                    status_text = await tr(user_id, 'overdue', days=abs(days_left))
                elif days_left == 0:
                    status_text = await tr(user_id, 'due_today')
                else:
                    status_text = await tr(user_id, 'due_in_days', days=days_left)

                if direction == 'owed':
                    person_text = await tr(user_id, 'debtor_name', person=debt['person'])
                else:
                    person_text = await tr(user_id, 'creditor_name', person=debt['person'])

                message_lines.append(
                    f"• {person_text}: {debt['amount']} {debt.get('currency', 'UZS')}\n"
                    f"  {status_text}"
                )

            message_text = '\n\n'.join(message_lines)

            print(f"📤 Отправка сообщения пользователю {user_id}")
            await self.bot.send_message(user_id, message_text)
            print(f"✅ Ежедневное напоминание отправлено пользователю {user_id}")

        except Exception as e:
            print(f"❌ Ошибка отправки ежедневного напоминания пользователю {user_id}: {e}")
            traceback.print_exc()
        finally:
            print("="*50 + "\n")

    async def _send_user_reminder(self, user_id: int, debts: list):
        """Отправить напоминание конкретному пользователю"""
        try:
            from app.keyboards import tr, main_menu, safe_str

            if len(debts) == 1:
                debt = debts[0]
                text = await tr(
                    user_id,
                    'single_reminder',
                    person=safe_str(debt['person']),
                    amount=safe_str(debt['amount']),
                    currency=safe_str(debt.get('currency', 'UZS')),
                    due=safe_str(debt['due'])
                )
            else:
                text = await tr(user_id, 'multiple_reminders', count=len(debts))
                for debt in debts:
                    text += f"\n• {safe_str(debt['person'])}: {safe_str(debt['amount'])} {safe_str(debt.get('currency', 'UZS'))}"

            kb = await main_menu(user_id)

            # основная попытка отправки
            await self.bot.send_message(user_id, text, reply_markup=kb)

        except TelegramBadRequest as e:
            if "chat not found" in str(e):
                print(f"❌ Пользователь {user_id} не найден (chat not found)")
            else:
                print(f"❌ BadRequest при отправке пользователю {user_id}: {e}")

        except TelegramForbiddenError:
            print(f"🚫 Пользователь {user_id} заблокировал бота")

        except TelegramRetryAfter as e:
            print(f"⏳ Flood control для {user_id}, ждем {e.retry_after} секунд")
            await asyncio.sleep(e.retry_after)
            # повторяем попытку
            return await self._send_user_reminder(user_id, debts)

        except Exception as e:
            print(f"⚠️ Неизвестная ошибка при отправке пользователю {user_id}: {e}")
            traceback.print_exc()

    async def schedule_all_reminders(self):
        """Перепланировать все напоминания для всех пользователей"""
        print("\n" + "="*70)
        print("🔄 ЗАПУСК: schedule_all_reminders")
        print("="*70)

        try:
            from app.database import get_all_users

            # Очищаем все существующие задачи
            existing_jobs = self.scheduler.get_jobs()
            print(f"🗑️ Существующих задач перед очисткой: {len(existing_jobs)}")

            removed_count = 0
            for job in existing_jobs:
                if job.id.startswith(('user_reminder_', 'user_currency_', 'general_reminders_', 'repeating_reminders')):
                    print(f"  🗑️ Удаляем задачу: {job.id}")
                    job.remove()
                    removed_count += 1

            print(f"✅ Удалено задач: {removed_count}")

            # Получаем всех пользователей
            users = await get_all_users()
            print(f"👥 Получено пользователей из БД: {len(users)}")

            debt_reminders_count = 0
            currency_reminders_count = 0

            # Планируем индивидуальные напоминания
            for user in users:
                user_id = user['user_id']


                # Напоминания о долгах
                notify_time = user.get('notify_time')


                if notify_time:
                    try:
                        hour, minute = map(int, notify_time.split(':'))

                        self.scheduler.add_job(
                            self.send_daily_reminders,
                            'cron',
                            hour=hour,
                            minute=minute,
                            timezone='Asia/Tashkent',  # ← И ТУТ
                            id=f'user_reminder_{user_id}',
                            args=[user_id],
                            replace_existing=True
                        )
                        debt_reminders_count += 1


                    except Exception as e:
                        print(f"  ❌ Ошибка планирования напоминаний о долгах: {e}")
                        traceback.print_exc()

                # Валютные уведомления
                currency_time = user.get('currency_notify_time')


                if currency_time:
                    try:
                        hour, minute = map(int, currency_time.split(':'))
                        print(f"  ⏰ Установка валютного уведомления на {hour:02d}:{minute:02d}")

                        self.scheduler.add_job(
                            self.send_currency_alerts,
                            'cron',
                            hour=hour,
                            minute=minute,
                            timezone='Asia/Tashkent',  # ← ДОБАВЬ ЭТУ СТРОКУ
                            id=f'user_currency_{user_id}',
                            args=[user_id],
                            replace_existing=True
                        )
                        currency_reminders_count += 1
                        print(f"  ✅ Валютное уведомление запланировано")

                    except Exception as e:
                        print(f"  ❌ Ошибка планирования валютных уведомлений: {e}")
                        traceback.print_exc()

            # ГЛОБАЛЬНЫЕ задачи
            print("\n🌐 Добавление глобальных задач:")

            print("  ➕ Добавление general_reminders_global")
            self.scheduler.add_job(
                self.send_general_reminders,
                'interval',
                minutes=1,
                timezone='Asia/Tashkent',
                id='general_reminders_global',
                replace_existing=True
            )

            print("  ➕ Добавление repeating_reminders_global")
            self.scheduler.add_job(
                self.send_repeating_reminders,
                'interval',
                minutes=1,
                timezone='Asia/Tashkent',
                id='repeating_reminders_global',
                replace_existing=True
            )

            print("  ➕ Добавление due_reminders")
            self.scheduler.add_job(
                self.send_due_reminders,
                'cron',
                hour='*',
                timezone='Asia/Tashkent',
                id='due_reminders',
                replace_existing=True
            )

            # Итоговая статистика
            all_jobs = self.scheduler.get_jobs()
            print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА:")
            print(f"   ✅ Напоминаний о долгах: {debt_reminders_count}")
            print(f"   ✅ Валютных уведомлений: {currency_reminders_count}")
            print(f"   ✅ Глобальных задач: 3")
            print(f"   📋 Всего активных задач: {len(all_jobs)}")



        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА в schedule_all_reminders: {e}")
            traceback.print_exc()
        finally:
            print("="*70 + "\n")

    async def send_broadcast_to_all_users(self, text: str, photo_id: str = None, admin_id: int = None):
        """Отправить рассылку всем пользователям"""
        if not self.bot:
            return 0, 0, []

        try:
            from app.database import get_all_users

            users = await get_all_users()
            success_count = 0
            error_count = 0
            blocked_users = []

            for user in users:
                user_id = user['user_id']
                try:
                    if photo_id:
                        await self.bot.send_photo(user_id, photo_id, caption=text)
                    else:
                        await self.bot.send_message(user_id, text)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    blocked_users.append(user_id)
                    print(f"❌ Ошибка отправки пользователю {user_id}: {e}")

                await asyncio.sleep(0.05)

            return success_count, error_count, blocked_users

        except Exception as e:
            print(f"❌ Ошибка в send_broadcast_to_all_users: {e}")
            return 0, 0, []

    async def send_scheduled_broadcast_with_stats(self, text: str, photo_id: str = None, admin_id: int = None):
        """Отправить запланированную рассылку со статистикой"""
        success, errors, blocked = await self.send_broadcast_to_all_users(text, photo_id, admin_id)

        if admin_id:
            try:
                stats_text = f"📢 Рассылка завершена!\n\n✅ Отправлено: {success}\n❌ Ошибок: {errors}"
                await self.bot.send_message(admin_id, stats_text)
            except Exception as e:
                print(f"❌ Ошибка отправки статистики админу {admin_id}: {e}")

    def add_job(self, *args, **kwargs):
        """Обёртка для add_job"""
        return self.scheduler.add_job(*args, **kwargs)

    async def send_general_reminders(self):
        """Проверка и отправка одноразовых напоминаний"""
        print("\n" + "=" * 50)
        print("⏰ ЗАПУСК: send_general_reminders")
        print("=" * 50)

        if not self.bot:
            print("❌ Bot не установлен в scheduler")
            return

        try:
            from app.database.crud import update_reminder
            from app.database.connection import AsyncSessionLocal  # 👈 Правильный импорт

            now = datetime.now().replace(second=0, microsecond=0)
            print(f"🕐 Текущее время: {now}")

            reminders = await get_due_reminders(now)
            print(f"📋 Получено напоминаний из БД: {len(reminders)}")

            if not reminders:
                print("ℹ️ Нет одноразовых напоминаний для отправки")
                return

            for idx, r in enumerate(reminders, 1):
                print(f"\n📝 Напоминание {idx}/{len(reminders)}:")
                print(f"   ID: {r['id']}")
                print(f"   user_id: {r['user_id']}")
                print(f"   text: {r['text']}")
                print(f"   due: {r['due']}")
                print(f"   is_active: {r.get('is_active', 'N/A')}")

                try:
                    # 👇 Создаём сессию для обновления
                    async with AsyncSessionLocal() as session:
                        print(f"   ⏳ Деактивация напоминания...")
                        updated = await update_reminder(session, r['id'], is_active=False)
                        print(f"   {'✅' if updated else '❌'} Деактивация: {updated}")

                    text = f"⏰ {r['text']}\n🕒 {r['due']}"
                    print(f"   📤 Отправка сообщения пользователю {r['user_id']}")
                    await self.bot.send_message(r['user_id'], text)
                    print(f"   ✅ Напоминание отправлено")

                except Exception as e:
                    print(f"   ❌ Ошибка отправки напоминания: {e}")
                    traceback.print_exc()

        except Exception as e:
            print(f"❌ Критическая ошибка в send_general_reminders: {e}")
            traceback.print_exc()
        finally:
            print("=" * 50 + "\n")

    async def send_currency_alerts(self, user_id: int):
        """Отправить валютное уведомление конкретному пользователю"""
        print("\n" + "=" * 50)
        print(f"💱 ЗАПУСК: send_currency_alerts для user_id={user_id}")
        print(f"🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🤖 Bot установлен: {self.bot is not None}")
        print("=" * 50)

        if not self.bot:
            print("❌ Bot не установлен в scheduler")
            return

        try:
            from app.utils.currency_api import format_currency_notification
            from app.keyboards import tr

            print(f"📥 Импорты успешны")
            print(f"🌐 Запрос валютных данных для user {user_id}...")

            message = await format_currency_notification(user_id, tr)

            print(f"📝 Сообщение сформировано:")
            print(f"   Длина: {len(message)} символов")
            print(f"   Первые 200 символов: {message[:200]}")

            print(f"📤 Попытка отправки боту...")
            result = await self.bot.send_message(user_id, message, reply_markup=main_menu)
            print(f"✅ Сообщение отправлено! Message ID: {result.message_id}")

        except Exception as e:
            print(f"❌ ОШИБКА валютного уведомления: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("=" * 50 + "\n")

    async def send_repeating_reminders(self):
        """Проверка и отправка повторяющихся напоминаний"""
        print("\n" + "="*50)
        print("🔁 ЗАПУСК: send_repeating_reminders")
        print("="*50)

        if not self.bot:
            print("❌ Bot не установлен в scheduler")
            return

        try:
            now = datetime.now().replace(second=0, microsecond=0)
            print(f"🕐 Текущее время: {now}")

            reminders = await get_due_repeating_reminders(now)
            print(f"📋 Получено повторяющихся напоминаний из БД: {len(reminders)}")

            if not reminders:
                print("ℹ️ Нет повторяющихся напоминаний для отправки")
                return

            for idx, r in enumerate(reminders, 1):
                print(f"\n📝 Повторяющееся напоминание {idx}/{len(reminders)}:")
                print(f"   ID: {r['id']}")
                print(f"   user_id: {r['user_id']}")
                print(f"   text: {r['text']}")
                print(f"   due: {r['due']}")
                print(f"   repeat: {r['repeat']}")
                print(f"   is_active: {r.get('is_active', 'N/A')}")

                user_id = r['user_id']

                try:
                    due_time = r['due']
                    if isinstance(due_time, datetime):
                        due_time = due_time.replace(second=0, microsecond=0)
                    print(f"   ⏰ due_time (normalized): {due_time}")

                    # Проверяем время
                    if due_time > now:
                        print(f"   ⏭️ ПРОПУСК: due в будущем ({due_time} > {now})")
                        continue

                    print(f"   ✅ Напоминание готово к отправке")

                    text = f"⏰ {r['text']}"
                    print(f"   📤 Отправка сообщения пользователю {user_id}")
                    await self.bot.send_message(user_id, text)
                    print(f"   ✅ Сообщение отправлено")

                    # Рассчитываем следующую дату
                    new_due = None
                    print(f"   🔄 Расчёт следующей даты (repeat={r['repeat']})")

                    if r['repeat'] == "daily":
                        new_due = due_time + timedelta(days=1)
                        print(f"   📅 Следующая дата (daily): {new_due}")

                    elif r['repeat'] == "monthly":
                        current_month = due_time.month
                        current_year = due_time.year

                        next_month = current_month + 1
                        next_year = current_year

                        if next_month > 12:
                            next_month = 1
                            next_year += 1

                        max_day = calendar.monthrange(next_year, next_month)[1]
                        next_day = min(due_time.day, max_day)

                        new_due = due_time.replace(year=next_year, month=next_month, day=next_day)
                        print(f"   📅 Следующая дата (monthly): {new_due}")

                    if new_due:
                        print(f"   💾 Обновление даты в БД...")
                        await update_reminder_due(r['id'], new_due)
                        print(f"   ✅ Дата обновлена на {new_due}")
                    else:
                        print(f"   ⚠️ Не удалось рассчитать новую дату")

                except Exception as e:
                    print(f"   ❌ Ошибка обработки напоминания: {e}")
                    traceback.print_exc()

        except Exception as e:
            print(f"❌ Критическая ошибка в send_repeating_reminders: {e}")
            traceback.print_exc()
        finally:
            print("="*50 + "\n")


# Создаем глобальный экземпляр планировщика
scheduler = ReminderScheduler()


# Глобальная функция для импорта в других модулях
async def schedule_all_reminders():
    """Глобальная функция для перепланирования всех напоминаний"""
    await scheduler.schedule_all_reminders()