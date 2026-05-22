import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
import config
from handlers.start import router as start_router
from handlers.download import router as download_router
#from handlers.admin import router as admin_router

import logging
import sys


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logging.getLogger("httpx").setLevel(logging.WARNING)

async def main():
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    #dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(download_router)

    logging.info("[INIT] The bot launched...")

    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())