"""
Планировщик напоминаний
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import asyncio


class ReminderScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
        self.bot = None
        self.started = False

    def set_bot(self, bot):
        """Установить экземпляр бота"""
        self.bot = bot

    async def start(self):
        """Запустить планировщик"""
        if not self.started:
            self.scheduler.start()
            self.started = True
            print("✅ Планировщик напоминаний запущен")

    async def stop(self):
        """Остановить планировщик"""
        if self.started:
            self.scheduler.shutdown()
            self.started = False
            print("🔴 Планировщик напоминаний остановлен")

    async def send_due_reminders(self):
        """Отправить напоминания о просроченных долгах"""
        if not self.bot:
            print("❌ Bot не установлен в scheduler")
            return

        try:
            # Импортируем здесь, чтобы избежать циклических импортов
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

    async def _send_user_reminder(self, user_id: int, debts: list):
        """Отправить напоминание конкретному пользователю"""
        try:
            from app.keyboards import tr, main_menu

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
        """Запланировать все напоминания для пользователей"""
        try:
            from app.database import get_all_users

            users = await get_all_users()

            # Очищаем старые задачи напоминаний
            for job in self.scheduler.get_jobs():
                if job.id == 'send_due_reminders':
                    job.remove()

            # Создаем единую задачу на каждый час для проверки напоминаний
            self.scheduler.add_job(
                self.send_due_reminders,
                'cron',
                hour='*',  # Каждый час
                minute=0,
                id='send_due_reminders'
            )

            print(f"✅ Запланированы напоминания для {len(users)} пользователей")

        except Exception as e:
            print(f"❌ Ошибка планирования напоминаний: {e}")

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


# Создаем глобальный экземпляр планировщика
scheduler = ReminderScheduler()