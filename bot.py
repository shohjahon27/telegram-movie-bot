"""Entrypoint. Run with: python bot.py

Loads config from .env, ensures MongoDB indexes exist, bootstraps seed
admins, and starts long-polling. That's the entire startup sequence — no
migration step, no separate build step.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher

import config
import database as db
from handlers import admin as admin_handlers
from handlers import user as user_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bot")


async def bootstrap_admins():
    for telegram_id in config.SEED_ADMIN_IDS:
        await db.create_admin(telegram_id, "", "super_admin", created_by=None)
    count = await db.count_active_admins()
    if count == 0:
        log.warning("No active admins exist. Set SEED_ADMIN_IDS in .env and restart, "
                    "or admin commands will be unusable.")
    else:
        log.info("%d active admin(s) ready.", count)


async def main():
    log.info("Connecting to MongoDB at %s ...", config.MONGO_URI)
    await db.init_indexes()
    log.info("MongoDB indexes ensured.")

    await bootstrap_admins()

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    # Admin router registered first so admin-only commands are matched
    # before the catch-all handlers in the user router.
    dp.include_router(admin_handlers.router)
    dp.include_router(user_handlers.router)

    me = await bot.get_me()
    log.info("Authorized as @%s (%s)", me.username, me.id)

    log.info("Starting long-polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Shutting down.")
