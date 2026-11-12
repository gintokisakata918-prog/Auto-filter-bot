import asyncio

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

import database
from config import Config

KINDS = {"document": "document", "video": "video", "audio": "audio"}


def is_admin(uid: int) -> bool:
    return uid in Config.ADMINS


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
    if doc and await database.save_file(doc):
        try:
            await msg.react("👍")
        except Exception:
            pass


@Client.on_message(filters.command("index") & filters.user(list(Config.ADMINS)))
async def manual_index(client: Client, msg: Message):
    if msg.reply_to_message:
        doc = build_doc(msg.reply_to_message)
        if not doc:
            return await msg.reply("<b>Reply to a file.</b>")
        ok = await database.save_file(doc)
        return await msg.reply(f"<b>{'Indexed' if ok else 'Already indexed'}</b> · <code>{doc['_id']}</code>",
                               parse_mode=ParseMode.HTML)

    parts = msg.text.split()
    if len(parts) != 3 or "-" not in parts[2]:
        return await msg.reply(
            "<b>Usage</b>\n"
            "<code>/index</code> — reply to a file\n"
            "<code>/index -1001234567890 1-50</code> — range in a channel",
            parse_mode=ParseMode.HTML,
        )

    try:
        chat_id = int(parts[1])
        start, end = (int(x) for x in parts[2].split("-", 1))
    except ValueError:
        return await msg.reply("<b>Bad range.</b>")

    status = await msg.reply(f"<b>Indexing</b> <code>{start}–{end}</code>…", parse_mode=ParseMode.HTML)
    added = skipped = 0
    for mid in range(start, end + 1):
        try:
            m = await client.get_messages(chat_id, mid)
        except Exception:
            continue
        if not m or m.empty:
            continue
        doc = build_doc(m)
        if doc and await database.save_file(doc):
            added += 1
        else:
            skipped += 1
        if added % 25 == 0:
            try:
                await status.edit_text(f"<b>Indexing…</b> added {added}", parse_mode=ParseMode.HTML)
            except Exception:
                pass
        await asyncio.sleep(0.2)

    await status.edit_text(f"<b>Done</b> · added {added} · skipped {skipped}", parse_mode=ParseMode.HTML)
