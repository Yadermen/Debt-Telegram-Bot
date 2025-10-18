from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
import asyncio

bot = Bot("8372682502:AAH2oYBezxPc_lxEemANcn3MRxx8l1jkivM")
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Отправляем приветственное сообщение
    sent_message = await message.answer("Привет! Я сейчас удалю это сообщение :)")

    # Подождём немного (например, 3 секунды)
    await asyncio.sleep(3)

    # Проверяем, что чат — личный
    if message.chat.type == "private":
        try:
            # Удаляем сообщение пользователя
            await message.delete()
            # Удаляем сообщение бота
            await sent_message.delete()
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

if __name__ == "__main__":
    dp.run_polling(bot)