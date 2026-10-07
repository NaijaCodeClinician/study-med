import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)
from aiohttp import web
from dotenv import load_dotenv

from src.bot.handlers.add import router as add_router
from src.bot.handlers.start import router as start_router

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

WEBHOOK_PATH = "/webhook"

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "10000"))


# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Environment validation
# ---------------------------------------------------------


def validate_environment() -> None:
    """Make sure required environment variables exist."""

    missing = []

    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")

    if not WEBHOOK_BASE_URL:
        missing.append("WEBHOOK_BASE_URL")

    if not WEBHOOK_SECRET:
        missing.append("WEBHOOK_SECRET")

    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )


# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------


async def health_check(request: web.Request) -> web.Response:
    """
    Render health-check endpoint.

    GET /health
    """

    return web.Response(
        text="StudyMed is running.",
        status=200,
    )


# ---------------------------------------------------------
# Webhook configuration
# ---------------------------------------------------------


async def configure_webhook(
    bot: Bot,
    webhook_url: str,
) -> None:
    """
    Configure Telegram's webhook.

    This runs after the HTTP server has started listening,
    so Render can detect the open port immediately.
    """

    try:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=False,
        )

        logger.info(
            "Telegram webhook successfully configured: %s",
            webhook_url,
        )

    except Exception:
        logger.exception(
            "Failed to configure Telegram webhook: %s",
            webhook_url,
        )


# ---------------------------------------------------------
# Webhook startup task
# ---------------------------------------------------------


async def webhook_startup(
    bot: Bot,
    webhook_url: str,
) -> None:
    """
    Wait briefly for the HTTP server to finish binding,
    then configure Telegram's webhook.

    The task is intentionally scheduled rather than awaited
    during server startup so Render can detect the open port.
    """

    await asyncio.sleep(0)

    await configure_webhook(
        bot=bot,
        webhook_url=webhook_url,
    )


# ---------------------------------------------------------
# Application creation
# ---------------------------------------------------------


def create_application(
    bot: Bot,
    dispatcher: Dispatcher,
) -> web.Application:
    """
    Build the aiohttp application.
    """

    app = web.Application()

    # -----------------------------------------------------
    # Health endpoint
    # -----------------------------------------------------

    app.router.add_get(
        "/health",
        health_check,
    )

    # -----------------------------------------------------
    # Telegram webhook handler
    # -----------------------------------------------------

    webhook_handler = SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )

    webhook_handler.register(
        app,
        path=WEBHOOK_PATH,
    )

    # -----------------------------------------------------
    # aiogram lifecycle integration
    # -----------------------------------------------------

    setup_application(
        app,
        dispatcher,
        bot=bot,
    )

    return app


# ---------------------------------------------------------
# Main application
# ---------------------------------------------------------


async def main() -> None:
    """
    Start StudyMed's webhook server.

    asyncio.run() owns the event loop.

    IMPORTANT:
    We do NOT call aiohttp.web.run_app() here because
    web.run_app() creates/manages its own event loop.
    """

    validate_environment()

    webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}{WEBHOOK_PATH}"

    # -----------------------------------------------------
    # Bot
    # -----------------------------------------------------

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    # -----------------------------------------------------
    # Dispatcher
    # -----------------------------------------------------

    dp = Dispatcher()

    # Register routers
    dp.include_routers(start_router,add_router)

    # -----------------------------------------------------
    # aiohttp application
    # -----------------------------------------------------

    app = create_application(
        bot=bot,
        dispatcher=dp,
    )

    # -----------------------------------------------------
    # Start aiohttp
    # -----------------------------------------------------

    runner = web.AppRunner(app)

    try:
        # Prepare application
        await runner.setup()

        # Bind server to Render's assigned port
        site = web.TCPSite(
            runner,
            host=HOST,
            port=PORT,
        )

        await site.start()

        logger.info(
            "StudyMed HTTP server is listening on %s:%s",
            HOST,
            PORT,
        )

        logger.info(
            "Health endpoint: %s/health",
            WEBHOOK_BASE_URL.rstrip("/"),
        )

        logger.info(
            "Webhook endpoint: %s",
            webhook_url,
        )

        # -------------------------------------------------
        # Configure Telegram AFTER the port is listening.
        # -------------------------------------------------

        await configure_webhook(
            bot=bot,
            webhook_url=webhook_url,
        )

        # -------------------------------------------------
        # Keep application alive.
        # -------------------------------------------------

        await asyncio.Event().wait()

    finally:
        logger.info("Shutting down StudyMed...")

        # Remove the webhook during shutdown.
        try:
            await bot.delete_webhook(
                drop_pending_updates=False,
            )

            logger.info("Telegram webhook removed.")

        except Exception:
            logger.exception("Failed to remove Telegram webhook.")

        # Clean up aiohttp / aiogram resources.
        await runner.cleanup()

        # Close Telegram HTTP session.
        await bot.session.close()

        logger.info("StudyMed shutdown complete.")


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("StudyMed stopped by user.")

    except Exception:
        logger.exception("StudyMed crashed during startup.")
        raise
