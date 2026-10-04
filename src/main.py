import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from src.bot.handlers.add import router as add_router
from src.bot.handlers.start import router as start_router

load_dotenv()

BOT_TOKEN = str(os.getenv("BOT_TOKEN"))


async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_routers(start_router, add_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
