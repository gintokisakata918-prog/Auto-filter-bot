import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import Message

import database
from config import Config

log = logging.getLogger("autofilter.index")
KINDS = ("document", "video", "audio")


def build_doc(msg: Message) -> dict | None:
    for kind in KINDS:
        media = getattr(msg, kind, None)
        if not media:
            continue
        return {
            "_id": media.file_unique_id,
            "file_id": media.file_id,
            "kind": kind,
            "name": getattr(media, "file_name", None) or f"{kind}_{media.file_unique_id}",
            "size": getattr(media, "file_size", 0) or 0,
            "mime_type": getattr(media, "mime_type", None),
            "channel": msg.chat.id,
            "channel_title": msg.chat.title,
            "message_id": msg.id,
        }
    return None


@Client.on_message(filters.channel & (filters.document | filters.video | filters.audio))
async def auto_index(client: Client, msg: Message):
    if Config.DB_CHANNELS and msg.chat.id not in Config.DB_CHANNELS:
        return
    doc = build_doc(msg)
    if doc:
        saved = await database.save_file(doc)
        if saved:
            log.info("Indexed new file: %s | channel=%s | message=%s", doc["name"], msg.chat.id, msg.id)
            try:
                await msg.react("👍")
            except Exception:
                pass


@Client.on_message(filters.command("index") & filters.user(list(Config.ADMINS)))
async def manual_index(client: Client, msg: Message):
    if msg.reply_to_message:
        doc = build_doc(msg.reply_to_message)
        if not doc:
            return await msg.reply("Reply to a video, document or audio file.")
        ok = await database.save_file(doc)
        return await msg.reply(
            f"<b>{'Indexed' if ok else 'Already indexed'}</b> · <code>{doc['_id']}</code>",
            parse_mode=ParseMode.HTML,
        )

    parts = msg.text.split()
    if len(parts) not in (2, 3):
        return await msg.reply(
            "<b>Usage</b>\n"
            "<code>/index -1001234567890</code> — index complete channel history\n"
            "<code>/index -1001234567890 1-500</code> — index selected message range\n"
            "Or reply to one file with <code>/index</code>.",
            parse_mode=ParseMode.HTML,
        )

    try:
        chat_id = int(parts[1])
        if len(parts) == 3:
            start, end = (int(x) for x in parts[2].split("-", 1))
            if start < 1 or end < start:
                raise ValueError
    except ValueError:
        return await msg.reply("Invalid channel ID or message range.")

    status = await msg.reply("<b>Connecting to channel…</b>", parse_mode=ParseMode.HTML)
    added = skipped = scanned = 0

    async def process(item: Message):
        nonlocal added, skipped, scanned
        scanned += 1
        doc = build_doc(item)
        if doc:
            if await database.save_file(doc):
                added += 1
            else:
                skipped += 1

    try:
        if len(parts) == 3:
            for mid in range(start, end + 1):
                try:
                    item = await client.get_messages(chat_id, mid)
                    if item and not item.empty:
                        await process(item)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception as e:
                    log.warning("Could not read message %s from %s: %s", mid, chat_id, e)
                if mid % 100 == 0:
                    await status.edit_text(
                        f"<b>Scanning</b> <code>{mid}/{end}</code>\n"
                        f"Added: <code>{added}</code> · skipped: <code>{skipped}</code>",
                        parse_mode=ParseMode.HTML,
                    )
                await asyncio.sleep(0.05)
        else:
            async for item in client.get_chat_history(chat_id):
                await process(item)
                if scanned % 100 == 0:
                    await status.edit_text(
                        f"<b>Scanning channel history…</b>\n"
                        f"Scanned: <code>{scanned}</code> · added: <code>{added}</code> · "
                        f"skipped: <code>{skipped}</code>",
                        parse_mode=ParseMode.HTML,
                    )
                await asyncio.sleep(0.05)
    except Exception as e:
        log.exception("Manual indexing failed for channel %s", chat_id)
        return await status.edit_text(
            f"<b>Indexing stopped.</b>\n<code>{type(e).__name__}: {e}</code>\n"
            f"Scanned: <code>{scanned}</code> · added: <code>{added}</code>",
            parse_mode=ParseMode.HTML,
        )

    await status.edit_text(
        f"<b>Indexing complete</b>\n"
        f"Scanned: <code>{scanned}</code>\n"
        f"Added: <code>{added}</code> · already indexed/no media: <code>{skipped}</code>\n"
        f"Total indexed files: <code>{await database.total_files()}</code>",
        parse_mode=ParseMode.HTML,
    )
