import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import database
from config import Config
from utils.fsub import keyboard as fsub_keyboard
from utils.helpers import caption, esc, result_keyboard, size, trim

RESULTS_TTL = 300
NO_RESULT = (
    "<b>Nothing found</b>\n"
    "<blockquote>No file matches <code>{q}</code>.</blockquote>\n"
    "<i>Try fewer words, or check the spelling.</i>"
)


async def _delete_later(message: Message, seconds: int):
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except Exception:
        pass


def _schedule_delete(message: Message, seconds: int):
    asyncio.create_task(_delete_later(message, seconds))


def is_search(msg: Message) -> bool:
    return bool(msg.text and 2 <= len(msg.text.strip()) <= 120)


@Client.on_message(filters.private & filters.text & ~filters.command(
    ["start", "help", "stats", "id", "index", "settings", "setphoto", "delphoto", "broadcast", "delete", "deleteall", "ban", "unban", "pmsearch", "pm_search", "groupsearch", "group_search"]))
async def pm_search(client: Client, msg: Message):
    if not await database.get_setting("pm_search", True):
        return
    if await database.is_banned(msg.from_user.id):
        return
    kb = await fsub_keyboard(client, msg.from_user.id)
    if kb:
        return await msg.reply("<b>Join to continue</b>", reply_markup=kb)
    await run_search(client, msg, msg.text.strip(), 0)


@Client.on_message(filters.group & filters.text & ~filters.via_bot & ~filters.service & ~filters.command(["pmsearch", "pm_search", "groupsearch", "group_search"]))
async def group_search(client: Client, msg: Message):
    if not await database.get_setting("group_search", True):
        return
    if not is_search(msg):
        return
    await run_search(client, msg, msg.text.strip(), 0)


async def run_search(client: Client, msg: Message, query: str, page: int):
    docs, total = await database.search(query, page * Config.PER_PAGE, Config.PER_PAGE)
    if not docs:
        sent = await msg.reply(NO_RESULT.format(q=esc(trim(query, 40))), parse_mode=ParseMode.HTML)
        _schedule_delete(sent, RESULTS_TTL)
        return
    head = (
        f"<b>{esc(trim(query, 40))}</b>\n"
        f"<blockquote>{total} match{'es' if total != 1 else ''} · page {page + 1}</blockquote>"
    )
    sent = await msg.reply(head, reply_markup=result_keyboard(docs, query, page, total), parse_mode=ParseMode.HTML)
    _schedule_delete(sent, RESULTS_TTL)


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
        _schedule_delete(cb.message, RESULTS_TTL)
    except MessageNotModified:
        pass
    await cb.answer()


@Client.on_callback_query(filters.regex(r"^send:"))
async def send_file(client: Client, cb: CallbackQuery):
    uid = cb.data.split(":", 1)[1]
    is_group = cb.message.chat.type != ChatType.PRIVATE
    destination = cb.from_user.id if is_group else cb.message.chat.id
    try:
        await deliver(client, cb.message, uid, target_chat_id=destination)
        await cb.answer("File sent to your PM. Check your private chat.")
    except Exception:
        if is_group:
            await cb.answer("I couldn't DM you. Open the bot and press START first, then try again.", show_alert=True)
        else:
            await cb.answer("Couldn't send this file. Please try again.", show_alert=True)


async def deliver(
    client: Client,
    msg: Message,
    uid: str,
    reply_to: int | None = None,
    target_chat_id: int | None = None,
):
    doc = await database.get_file(uid)
    if not doc:
        return await msg.reply("<b>File is gone.</b> It was removed from the index.")
    destination = target_chat_id or msg.chat.id
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(
        "Open in PM", url=f"https://t.me/{Config.BOT_USERNAME}?start=file_{uid}")]]) \
        if msg.chat.type != ChatType.PRIVATE and destination == msg.chat.id and Config.BOT_USERNAME else None
    protect = await database.get_setting("protect_content", Config.PROTECT)
    warning = (
        "\n\n⚠️ <b>Temporary file</b>\n"
        "This file will be automatically deleted in 10 minutes. "
        "Please save it to your device before the time expires."
    )
    common = dict(
        caption=caption(doc) + warning,
        parse_mode=ParseMode.HTML,
        protect_content=bool(protect),
        reply_markup=kb,
    )
    if reply_to and destination == msg.chat.id:
        common["reply_to_message_id"] = reply_to
    if doc.get("kind") == "video":
        sent = await client.send_video(destination, doc["file_id"], **common)
    elif doc.get("kind") == "audio":
        sent = await client.send_audio(destination, doc["file_id"], **common)
    else:
        sent = await client.send_document(destination, doc["file_id"],
                                          file_name=doc.get("name"), **common)
    if Config.AUTO_DELETE:
        _schedule_delete(sent, Config.AUTO_DELETE)
