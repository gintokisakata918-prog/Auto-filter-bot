import asyncio
import logging

from pyrogram import Client

import database
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("autofilter")

app = Client(
    "autofilter",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins={"root": "plugins"},
)


async def main():
    await database.ensure_indexes()
    async with app:
        me = await app.get_me()
        log.info("running as @%s · %s files indexed", me.username, await database.total_files())
        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
