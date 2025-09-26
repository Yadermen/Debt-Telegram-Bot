"""
Планировщик напоминаний
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import asyncio
from app.database.models import Reminder
from app.database.crud import (
    get_due_reminders,
    get_due_repeating_reminders,
    update_reminder_due,
    delete_reminder
)


class ReminderScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
        self.bot = None
        self.started = False
        self.running = False

    def set_bot(self, bot):
        """Установить экземпляр бота"""
        self.bot = bot

    async def start(self):
        """Запустить планировщик"""
        if not self.started:
            self.scheduler.start()
            self.started = True
            self.running = True
            print("✅ Планировщик напоминаний запущен")

    async def stop(self):
        """Остановить планировщик"""
        if self.started:
            self.scheduler.shutdown()
            self.started = False
            self.running = False
            print("🔴 Планировщик напоминаний остановлен")

    async def send_due_reminders(self):
        """Отправить напоминания о просроченных долгах"""
        if not self.bot:
            print("❌ Bot не установлен в scheduler")
            return

        try:
            from app.database import get_due_debts_for_reminders, get_user_data
            from app.keyboards import tr, safe_str

            print("📅 Проверка просроченных долгов...")

            # Получаем долги, которые просрочены или просрочиваются сегодня
            today = datetime.now().strftime('%Y-%m-%d')
            due_debts = await get_due_debts_for_reminders(today)

            if not due_debts:
                print("✅ Просроченных долгов нет")
                return

            print(f"📋 Найдено {len(due_debts)} просроченных долгов")

            # Группируем долги по пользователям
            user_debts = {}
            for debt in due_debts:
                user_id = debt['user_id']
                if user_id not in user_debts:
                    user_debts[user_id] = []
                user_debts[user_id].append(debt)

            # Отправляем напоминания каждому пользователю
            for user_id, debts in user_debts.items():
                try:
                    await self._send_user_reminder(user_id, debts)
                    print(f"✅ Напоминание отправлено пользователю {user_id}")
                except Exception as e:
                    print(f"❌ Ошибка отправки напоминания пользователю {user_id}: {e}")

        except Exception as e:
            print(f"❌ Ошибка в send_due_reminders: {e}")

    async def send_daily_reminders(self, user_id: int):
        """
        Отправить ежедневные напоминания конкретному пользователю
        """
        if not self.bot:
            print("❌ Bot не установлен в scheduler")
            return

        try:
            from app.database import get_open_debts
            from app.keyboards import tr, safe_str

            # Получаем долги пользователя
            debts = await get_open_debts(user_id)

            if not debts:
                return

            # Фильтруем долги, которые скоро истекают (в течение 3 дней)
            today = datetime.now().date()
            upcoming_debts = []

            for debt in debts:
                try:
                    due_date = datetime.strptime(debt['due'], '%Y-%m-%d').date()
                    days_left = (due_date - today).days

                    if days_left <= 3:  # Напоминаем за 3 дня и менее
                        upcoming_debts.append((debt, days_left))
                except:
                    continue

            if not upcoming_debts:
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

                if direction == 'owed':  # Мне должны
                    person_text = await tr(user_id, 'debtor_name', person=debt['person'])
                else:  # Я должен
                    person_text = await tr(user_id, 'creditor_name', person=debt['person'])

                message_lines.append(
                    f"• {person_text}: {debt['amount']} {debt.get('currency', 'UZS')}\n"
                    f"  {status_text}"
                )

            message_text = '\n\n'.join(message_lines)

            # Отправляем напоминание
            await self.bot.send_message(user_id, message_text)
            print(f"✅ Ежедневное напоминание отправлено пользователю {user_id}")

        except Exception as e:
            print(f"❌ Ошибка отправки ежедневного напоминания пользователю {user_id}: {e}")

    async def _send_user_reminder(self, user_id: int, debts: list):
        """Отправить напоминание конкретному пользователю"""
        try:
            from app.keyboards import tr, main_menu, safe_str

            if len(debts) == 1:
                debt = debts[0]
                text = await tr(user_id, 'single_reminder',
                              person=safe_str(debt['person']),
                              amount=safe_str(debt['amount']),
                              currency=safe_str(debt.get('currency', 'UZS')),
                              due=safe_str(debt['due']))
            else:
                text = await tr(user_id, 'multiple_reminders', count=len(debts))
                for debt in debts:
                    text += f"\n• {safe_str(debt['person'])}: {safe_str(debt['amount'])} {safe_str(debt.get('currency', 'UZS'))}"

            kb = await main_menu(user_id)
            await self.bot.send_message(user_id, text, reply_markup=kb)

        except Exception as e:
            print(f"❌ Ошибка отправки напоминания пользователю {user_id}: {e}")

    async def schedule_all_reminders(self):
        """
        Перепланировать все напоминания для всех пользователей
        Вызывается при изменении времени уведомлений пользователя
        """
        try:
            from app.database import get_all_users

            # Очищаем все существующие задачи пользовательских напоминаний
            for job in self.scheduler.get_jobs():
                if job.id.startswith(('user_reminder_', 'user_currency_', 'general_reminders_', 'repeating_reminders')):
                    job.remove()

            print("🔄 Перепланирование всех пользовательских напоминаний...")

            # Получаем всех пользователей
            users = await get_all_users()
            scheduled_count = 0

            for user in users:
                user_id = user['user_id']
                notify_time = user.get('notify_time')

                if not notify_time:
                    continue

                try:
                    hour, minute = map(int, notify_time.split(':'))

                    # Ежедневные напоминания о долгах
                    self.scheduler.add_job(
                        self.send_daily_reminders,
                        'cron',
                        hour=hour,
                        minute=minute,
                        id=f'user_reminder_{user_id}',
                        args=[user_id],
                        replace_existing=True
                    )

                    # Валютные уведомления
                    self.scheduler.add_job(
                        self.send_currency_alerts,
                        'cron',
                        hour=hour,
                        minute=minute,
                        id=f'user_currency_{user_id}',
                        args=[user_id],
                        replace_existing=True
                    )

                    # Проверка пользовательских напоминаний (одноразовые)
                    self.scheduler.add_job(
                        self.send_general_reminders,
                        'interval',
                        minutes=1,
                        id=f'general_reminders_{user_id}',
                        replace_existing=True
                    )

                    # Проверка повторяющихся напоминаний
                    self.scheduler.add_job(
                        self.send_repeating_reminders,
                        'interval',
                        minutes=1,
                        id=f'repeating_reminders_{user_id}',
                        replace_existing=True
                    )

                    scheduled_count += 1

                except Exception as e:
                    print(f"❌ Ошибка планирования напоминаний для пользователя {user_id}: {e}")

            # Общая проверка просроченных долгов каждый час
            self.scheduler.add_job(
                self.send_due_reminders,
                'cron',
                hour='*',
                id='due_reminders',
                replace_existing=True
            )

            print(f"✅ Перепланирование завершено. Запланировано {scheduled_count} пользовательских напоминаний")

        except Exception as e:
            print(f"❌ Ошибка в schedule_all_reminders: {e}")

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
                user_id = user['text']
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

                # Небольшая задержка между отправками
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
        """Проверка и отправка пользовательских напоминаний (не долги)"""
        if not self.bot:
            print("❌ Bot не установлен в scheduler")
            return

        try:
            from app.database.crud import get_due_reminders  # нужно реализовать
            from app.keyboards import tr

            now = datetime.now().replace(second=0, microsecond=0)
            reminders = await get_due_reminders(now)

            if not reminders:
                return

            for r in reminders:
                try:
                    text = f"⏰ {r.text}\n🕒 {r.due}"
                    await self.bot.send_message(r.user_id, text)
                    # если одноразовое — удалить, если повторяющееся — пересчитать due
                except Exception as e:
                    print(f"❌ Ошибка отправки напоминания {r.id} пользователю {r.user_id}: {e}")

        except Exception as e:
            print(f"❌ Ошибка в send_general_reminders: {e}")

    async def send_currency_alerts(self, user_id: int):
        """Отправить валютное уведомление конкретному пользователю"""
        if not self.bot:
            return

        try:
            from app.database.crud import get_user_currency_settings
            from app.keyboards import tr

            settings = await get_user_currency_settings(user_id)
            if not settings:
                return

            # допустим, settings = {"base": "USD", "quote": "UZS"}
            import httpx
            async with httpx.AsyncClient() as client:
                url = f"https://api.exchangerate.host/latest?base={settings['base']}&symbols={settings['quote']}"
                resp = await client.get(url)
                rate = resp.json()["rates"][settings["quote"]]

            text = f"💱 {settings['base']}/{settings['quote']} = {rate:.2f}"
            await self.bot.send_message(user_id, text)

        except Exception as e:
            print(f"❌ Ошибка валютного уведомления для {user_id}: {e}")

    async def send_repeating_reminders(self):
        """Проверка и отправка повторяющихся напоминаний"""
        if not self.bot:
            return

        try:
            from app.database.crud import get_due_repeating_reminders, update_reminder_due
            from app.keyboards import tr, safe_str
            from datetime import datetime, timedelta
            import calendar

            now = datetime.now().replace(second=0, microsecond=0)
            reminders = await get_due_repeating_reminders(now)

            for r in reminders:
                user_id = r.user_id
                try:
                    # мультиязычный текст
                    text = await tr(user_id, "reminder_message", reminder=safe_str(r.text))
                    await self.bot.send_message(user_id, f"⏰ {text}")

                    # перенос даты
                    if r.repeat == "daily":
                        new_due = r.due + timedelta(days=1)
                    elif r.repeat == "monthly":
                        year = r.due.year + (r.due.month // 12)
                        month = (r.due.month % 12) + 1
                        day = min(r.due.day, calendar.monthrange(year, month)[1])
                        new_due = r.due.replace(year=year, month=month, day=day)
                    else:
                        continue

                    await update_reminder_due(r.id, new_due)

                except Exception as e:
                    print(f"❌ Ошибка повторного напоминания {r.id} пользователю {user_id}: {e}")

        except Exception as e:
            print(f"❌ Ошибка в send_repeating_reminders: {e}")


# Создаем глобальный экземпляр планировщика
scheduler = ReminderScheduler()


# Глобальная функция для импорта в других модулях
async def schedule_all_reminders():
    """
    Глобальная функция для перепланирования всех напоминаний
    """
    await scheduler.schedule_all_reminders()