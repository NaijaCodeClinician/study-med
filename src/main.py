import asyncio
import logging
import os
import sys

from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)
from dotenv import load_dotenv

from src.bot.handlers.add import router as add_router
from src.bot.handlers.start import router as start_router


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

WEBHOOK_PATH = "/webhook"

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "10000"))


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set.")

    if not WEBHOOK_BASE_URL:
        raise RuntimeError("WEBHOOK_BASE_URL is not set.")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    dp = Dispatcher()

    dp.include_routers(
        start_router,
        add_router,
    )

    webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}{WEBHOOK_PATH}"

    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=False,
    )

    app = web.Application()

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )

    webhook_handler.register(
        app,
        path=WEBHOOK_PATH,
    )

    setup_application(
        app,
        dp,
        bot=bot,
    )

    logging.info("StudyMed webhook: %s", webhook_url)
    logging.info("Listening on %s:%s", HOST, PORT)

    web.run_app(
        app,
        host=HOST,
        port=PORT,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
    )

    asyncio.run(main())
