from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQuery, InlineQueryResultDocument,
)

import database
from config import Config
from utils.helpers import caption, size, trim


@Client.on_inline_query()
async def inline(client: Client, q: InlineQuery):
    query = q.query.strip()
    if not query:
        return await q.answer(
            [], switch_pm_text="Type a title to search", switch_pm_parameter="start", cache_time=5
        )

    offset = int(q.offset or 0)
    docs, total = await database.search(query, offset, Config.PER_PAGE)

    if not docs:
        return await q.answer(
            [], switch_pm_text=f"No match for “{trim(query, 25)}”",
            switch_pm_parameter="start", cache_time=5,
        )

    results = []
    for doc in docs:
        results.append(
            InlineQueryResultDocument(
                id=doc["_id"],
                title=trim(doc.get("name"), 60),
                description=f"{size(doc.get('size'))} · tap to send",
                document_file_id=doc["file_id"],
                mime_type=doc.get("mime_type") or "application/octet-stream",
                caption=caption(doc),
                parse_mode=ParseMode.HTML,
            )
        )

    pages = max(1, -(-total // Config.PER_PAGE))
    nxt = str(offset + Config.PER_PAGE) if offset + Config.PER_PAGE < total else ""

    await q.answer(
        results,
        next_offset=nxt,
        is_personal=True,
        cache_time=15,
        switch_pm_text=f"{total} result{'s' if total != 1 else ''} · page {offset // Config.PER_PAGE + 1}/{pages}",
        switch_pm_parameter="start",
    )
