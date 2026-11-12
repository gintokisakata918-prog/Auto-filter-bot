from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

import database
from config import Config
from utils.fsub import keyboard as fsub_keyboard
from utils.helpers import start_keyboard

START_TEXT = (
    "<b>◈ AutoFilter</b>\n"
    "<blockquote>A quiet little search engine for the files in my channels.</blockquote>\n"
    "Send a title, or a season and episode number, and I'll pull up the matches.\n\n"
    "<i>Tip: tap the button below to search without leaving this chat.</i>"
)

HELP_TEXT = (
    "<b>How it works</b>\n\n"
    "<b>1.</b> Type the name of what you want — <i>frieren 1080p</i>, <i>s02e04</i>, whatever you remember.\n"
    "<b>2.</b> Matches come back as a numbered list.\n"
    "<b>3.</b> Tap a number and the file lands in this chat.\n\n"
    "<b>Searching inside a group</b>\n"
    "Add me to the group and search the same way. I only answer when a search is plausible, so I don't spam.\n\n"
    "<b>Inline mode</b>\n"
    "Type my username in any chat, press space, then your query. Results can be sent anywhere."
)


@Client.on_message(filters.command("start") & filters.private)
async def start(client: Client, msg: Message):
    if await database.is_banned(msg.from_user.id):
        return await msg.reply("<b>You're banned.</b> Ask an admin to unban you.")

    await database.add_user(msg.from_user.id, msg.from_user.first_name or "")

    args = msg.text.split(maxsplit=1)
    payload = args[1].strip() if len(args) > 1 else ""

    kb = await fsub_keyboard(client, msg.from_user.id)
    if kb:
        return await msg.reply("<b>Join to continue</b>", reply_markup=kb)

    if payload.startswith("file_"):
        from plugins.search import deliver
        return await deliver(client, msg, payload[5:])

    await msg.reply_photo(Config.START_PIC, caption=START_TEXT, reply_markup=start_keyboard()) \
        if Config.START_PIC else await msg.reply(START_TEXT, reply_markup=start_keyboard())


@Client.on_callback_query(filters.regex("^(help|fsub|noop|close)$"))
async def misc(client: Client, cb: CallbackQuery):
    data = cb.data
    if data == "help":
        await cb.message.edit_text(HELP_TEXT)
    elif data == "close":
        await cb.message.delete()
    elif data == "noop":
        await cb.answer()
    elif data == "fsub":
        kb = await fsub_keyboard(client, cb.from_user.id)
        if kb:
            await cb.answer("Not yet", show_alert=True)
        else:
            await cb.message.edit_text(START_TEXT, reply_markup=start_keyboard())
