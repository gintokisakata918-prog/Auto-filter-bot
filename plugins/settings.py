from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import database
from config import Config

ADMIN_ONLY = filters.user(list(Config.ADMINS))


async def settings_markup():
    protect = bool(await database.get_setting("protect_content", Config.PROTECT))
    photo = await database.get_setting("start_pic", Config.START_PIC)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Protect Content: {'ON' if protect else 'OFF'}", callback_data="setting:protect")],
        [InlineKeyboardButton(f"Start Photo: {'SET' if photo else 'NOT SET'}", callback_data="setting:photo")],
        [InlineKeyboardButton("Close", callback_data="setting:close")],
    ])


@Client.on_message(filters.command("settings") & ADMIN_ONLY)
async def settings_panel(_, msg: Message):
    await msg.reply(
        "<b>⚙️ Bot Settings</b>\nChoose an option below. Changes are saved in MongoDB.",
        reply_markup=await settings_markup(),
    )


@Client.on_callback_query(filters.regex(r"^setting:"))
async def settings_callback(_, cb: CallbackQuery):
    if cb.from_user.id not in Config.ADMINS:
        return await cb.answer("Admins only.", show_alert=True)
    action = cb.data.split(":", 1)[1]
    if action == "protect":
        current = bool(await database.get_setting("protect_content", Config.PROTECT))
        await database.set_setting("protect_content", not current)
        await cb.answer(f"Protect Content {'ON' if not current else 'OFF'}")
        return await cb.message.edit_reply_markup(await settings_markup())
    if action == "photo":
        return await cb.answer("Reply to a photo with /setphoto to set it; use /delphoto to remove it.", show_alert=True)
    if action == "close":
        await cb.message.delete()
        return await cb.answer()


@Client.on_message(filters.command("setphoto") & ADMIN_ONLY)
async def set_start_photo(_, msg: Message):
    target = msg.reply_to_message
    if not target or not target.photo:
        return await msg.reply("Reply to a photo with /setphoto.")
    await database.set_setting("start_pic", target.photo.file_id)
    await msg.reply("✅ Start photo saved.")


@Client.on_message(filters.command("delphoto") & ADMIN_ONLY)
async def delete_start_photo(_, msg: Message):
    await database.set_setting("start_pic", "")
    await msg.reply("✅ Start photo removed. Bot will use START_PIC from environment, if set.")
