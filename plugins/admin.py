import asyncio

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import Message

import database
from config import Config

ADMIN_ONLY = filters.user(list(Config.ADMINS))


@Client.on_message(filters.command("stats") & ADMIN_ONLY)
async def stats(_, msg: Message):
    await msg.reply(
        f"<b>Index</b> <code>{await database.total_files()}</code> files\n"
        f"<b>Users</b> <code>{await database.total_users()}</code>\n"
        f"<b>Groups</b> <code>{await database.total_chats()}</code>\n"
        f"<b>Protect</b> <code>{Config.PROTECT}</code>\n"
        f"<b>Auto-delete</b> <code>{Config.AUTO_DELETE}s</code>",
        parse_mode=ParseMode.HTML,
    )


@Client.on_message(filters.command("id") & ADMIN_ONLY)
async def get_id(_, msg: Message):
    lines = [f"<b>Current chat ID:</b> <code>{msg.chat.id}</code>"]
    if msg.reply_to_message:
        forwarded_chat = getattr(msg.reply_to_message, "forward_from_chat", None)
        if forwarded_chat:
            lines.append(f"<b>Forwarded channel ID:</b> <code>{forwarded_chat.id}</code>")
        elif msg.reply_to_message.sender_chat:
            lines.append(f"<b>Sender channel ID:</b> <code>{msg.reply_to_message.sender_chat.id}</code>")
        elif msg.reply_to_message.from_user:
            lines.append(f"<b>Replied user ID:</b> <code>{msg.reply_to_message.from_user.id}</code>")
    await msg.reply("\n".join(lines), parse_mode=ParseMode.HTML)


@Client.on_message(filters.command("delete") & ADMIN_ONLY)
async def delete_one(_, msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply("<b>Usage</b> <code>/delete &lt;file_id&gt;</code>", parse_mode=ParseMode.HTML)
    ok = await database.delete_file(parts[1].strip())
    await msg.reply("<b>Deleted</b>" if ok else "<b>Not in index</b>", parse_mode=ParseMode.HTML)


@Client.on_message(filters.command("deleteall") & ADMIN_ONLY)
async def delete_all(_, msg: Message):
    n = await database.delete_all()
    await msg.reply(f"<b>Wiped</b> <code>{n}</code> files", parse_mode=ParseMode.HTML)


@Client.on_message(filters.command("ban") & ADMIN_ONLY)
async def ban(_, msg: Message):
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message and msg.reply_to_message.from_user else None
    if not uid:
        return await msg.reply("<b>Reply to a user.</b>")
    await database.ban(uid)
    await msg.reply(f"<b>Banned</b> <code>{uid}</code>", parse_mode=ParseMode.HTML)


@Client.on_message(filters.command("unban") & ADMIN_ONLY)
async def unban(_, msg: Message):
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message and msg.reply_to_message.from_user else None
    if not uid:
        return await msg.reply("<b>Reply to a user.</b>")
    await database.unban(uid)
    await msg.reply(f"<b>Unbanned</b> <code>{uid}</code>", parse_mode=ParseMode.HTML)


@Client.on_message(filters.command(["enable", "disable"]) & ADMIN_ONLY)
async def toggle(_, msg: Message):
    on = msg.text.startswith("/enable")
    await database.set_chat(msg.chat.id, on)
    await msg.reply(f"<b>{'Enabled' if on else 'Disabled'} here.</b>")


@Client.on_message(filters.command(["pmsearch", "pm_search"]) & ADMIN_ONLY)
async def toggle_pm_search(_, msg: Message):
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) == 1 or parts[1].strip().lower() not in {"on", "off"}:
        current = bool(await database.get_setting("pm_search", True))
        return await msg.reply(
            f"<b>PM search:</b> <code>{'ON' if current else 'OFF'}</code>\n"
            "Use <code>/pmsearch on</code> or <code>/pmsearch off</code>.",
            parse_mode=ParseMode.HTML,
        )
    enabled = parts[1].strip().lower() == "on"
    await database.set_setting("pm_search", enabled)
    await msg.reply(f"<b>PM search {'enabled' if enabled else 'disabled'}.</b>", parse_mode=ParseMode.HTML)


@Client.on_message(filters.command(["groupsearch", "group_search"]) & ADMIN_ONLY)
async def toggle_group_search(_, msg: Message):
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) == 1 or parts[1].strip().lower() not in {"on", "off"}:
        current = bool(await database.get_setting("group_search", True))
        return await msg.reply(
            f"<b>Group search:</b> <code>{'ON' if current else 'OFF'}</code>\n"
            "Use <code>/groupsearch on</code> or <code>/groupsearch off</code>.\n"
            "<i>Individual groups must also be enabled with /enable.</i>",
            parse_mode=ParseMode.HTML,
        )
    enabled = parts[1].strip().lower() == "on"
    await database.set_setting("group_search", enabled)
    await msg.reply(f"<b>Group search {'enabled' if enabled else 'disabled'} globally.</b>", parse_mode=ParseMode.HTML)


@Client.on_message(filters.command("broadcast") & ADMIN_ONLY)
async def broadcast(client: Client, msg: Message):
    if not msg.reply_to_message:
        return await msg.reply("<b>Reply to the message to broadcast.</b>")

    targets = await database.all_users() + await database.all_chats()
    status = await msg.reply(f"<b>Sending to {len(targets)}…</b>", parse_mode=ParseMode.HTML)
    ok = fail = 0
    for i, cid in enumerate(targets, 1):
        try:
            await msg.reply_to_message.copy(cid)
            ok += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            fail += 1
        except Exception:
            fail += 1
        if i % 40 == 0:
            try:
                await status.edit_text(f"<b>{i}/{len(targets)}</b> · ok {ok} · fail {fail}", parse_mode=ParseMode.HTML)
            except Exception:
                pass
    await status.edit_text(f"<b>Done</b> · ok {ok} · fail {fail}", parse_mode=ParseMode.HTML)
