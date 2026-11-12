from pyrogram import Client
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config


async def missing(client: Client, user_id: int) -> list:
    out = []
    for chat in Config.FORCE_SUB:
        try:
            await client.get_chat_member(chat, user_id)
        except UserNotParticipant:
            try:
                info = await client.get_chat(chat)
                link = info.invite_link or (f"https://t.me/{info.username}" if info.username else None)
                out.append((info.title, link))
            except Exception:
                out.append((str(chat), None))
        except Exception:
            continue
    return out


async def keyboard(client: Client, user_id: int) -> InlineKeyboardMarkup | None:
    chats = await missing(client, user_id)
    if not chats:
        return None
    rows = [[InlineKeyboardButton(f"Join {t}", url=u)] for t, u in chats if u]
    rows.append([InlineKeyboardButton("Try again", callback_data="fsub")])
    return InlineKeyboardMarkup(rows)
