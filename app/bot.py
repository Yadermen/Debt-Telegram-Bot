import asyncio
from aiogram import Bot, Dispatcher
from config import load_config
from handlers import setup_routers

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Tashkent'))

async def main():
    config = load_config()
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()

    # Сохраняем конфиг для использования в хендлерах
    dp["config"] = config

    dp.include_router(setup_routers())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())