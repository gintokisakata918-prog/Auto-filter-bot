from pyrogram import Client, filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import database
from config import Config
from utils.fsub import keyboard as fsub_keyboard
from utils.helpers import caption, esc, result_keyboard, size, trim

NO_RESULT = (
    "<b>Nothing found</b>\n"
    "<blockquote>No file matches <code>{q}</code>.</blockquote>\n"
    "<i>Try fewer words, or check the spelling.</i>"
)


def is_search(msg: Message) -> bool:
    return bool(msg.text and 2 <= len(msg.text.strip()) <= 120)


@Client.on_message(filters.private & filters.text & ~filters.command(
    ["start", "help", "stats", "id", "index", "settings", "setphoto", "delphoto", "broadcast", "delete", "deleteall", "ban", "unban"]))
async def pm_search(client: Client, msg: Message):
    if await database.is_banned(msg.from_user.id):
        return
    kb = await fsub_keyboard(client, msg.from_user.id)
    if kb:
        return await msg.reply("<b>Join to continue</b>", reply_markup=kb)
    await run_search(client, msg, msg.text.strip(), 0)


@Client.on_message(filters.group & filters.text & ~filters.via_bot & ~filters.service)
async def group_search(client: Client, msg: Message):
    if not is_search(msg):
        return
    if not await database.chat_enabled(msg.chat.id):
        return
    await run_search(client, msg, msg.text.strip(), 0)


async def run_search(client: Client, msg: Message, query: str, page: int):
    docs, total = await database.search(query, page * Config.PER_PAGE, Config.PER_PAGE)
    if not docs:
        return await msg.reply(NO_RESULT.format(q=esc(trim(query, 40))), parse_mode=ParseMode.HTML)
    head = (
        f"<b>{esc(trim(query, 40))}</b>\n"
        f"<blockquote>{total} match{'es' if total != 1 else ''} · page {page + 1}</blockquote>"
    )
    await msg.reply(head, reply_markup=result_keyboard(docs, query, page, total), parse_mode=ParseMode.HTML)


@Client.on_callback_query(filters.regex(r"^page:"))
async def paginate(client: Client, cb: CallbackQuery):
    _, page, query = cb.data.split(":", 2)
    page = int(page)
    docs, total = await database.search(query, page * Config.PER_PAGE, Config.PER_PAGE)
    if not docs:
        return await cb.answer("That page is gone", show_alert=True)
    head = (
        f"<b>{esc(trim(query, 40))}</b>\n"
        f"<blockquote>{total} match{'es' if total != 1 else ''} · page {page + 1}</blockquote>"
    )
    try:
        await cb.message.edit_text(head, reply_markup=result_keyboard(docs, query, page, total),
                                   parse_mode=ParseMode.HTML)
    except MessageNotModified:
        pass
    await cb.answer()


@Client.on_callback_query(filters.regex(r"^send:"))
async def send_file(client: Client, cb: CallbackQuery):
    await cb.answer("Sending…")
    await deliver(client, cb.message, cb.data.split(":", 1)[1], reply_to=cb.message.id)


async def deliver(client: Client, msg: Message, uid: str, reply_to: int | None = None):
    doc = await database.get_file(uid)
    if not doc:
        return await msg.reply("<b>File is gone.</b> It was removed from the index.")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(
        "Open in PM", url=f"https://t.me/{Config.BOT_USERNAME}?start=file_{uid}")]]) \
        if msg.chat.type != ChatType.PRIVATE and Config.BOT_USERNAME else None
    protect = await database.get_setting("protect_content", Config.PROTECT)
    common = dict(
        caption=caption(doc),
        parse_mode=ParseMode.HTML,
        protect_content=bool(protect),
        reply_markup=kb,
    )
    if reply_to:
        common["reply_to_message_id"] = reply_to
    if doc.get("kind") == "video":
        sent = await client.send_video(msg.chat.id, doc["file_id"], **common)
    elif doc.get("kind") == "audio":
        sent = await client.send_audio(msg.chat.id, doc["file_id"], **common)
    else:
        sent = await client.send_document(msg.chat.id, doc["file_id"],
                                          file_name=doc.get("name"), **common)
    if Config.AUTO_DELETE:
        import asyncio
        await asyncio.sleep(Config.AUTO_DELETE)
        try:
            await sent.delete()
        except Exception:
            pass
