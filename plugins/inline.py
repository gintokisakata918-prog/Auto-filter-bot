import logging

from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import (
    InlineQuery,
    InlineQueryResultCachedDocument,
)

import database
from config import Config
from utils.helpers import caption, size, trim

log = logging.getLogger("autofilter.inline")


@Client.on_inline_query()
async def inline(client: Client, q: InlineQuery):
    query = (q.query or "").strip()

    if not query:
        return await q.answer(
            results=[],
            cache_time=3,
            switch_pm_text="Type a title to search",
            switch_pm_parameter="start",
        )

    try:
        offset = max(0, int(q.offset or 0))
        docs, total = await database.search(query, offset, Config.PER_PAGE)

        if not docs:
            return await q.answer(
                results=[],
                is_personal=True,
                cache_time=5,
                switch_pm_text=f"No results for {trim(query, 25)}",
                switch_pm_parameter="start",
            )

        results = []
        for doc in docs:
            file_id = doc.get("file_id")
            if not file_id:
                continue

            name = doc.get("name") or "Unnamed file"
            file_size = size(doc.get("size"))

            results.append(
                InlineQueryResultCachedDocument(
                    id=str(doc.get("_id") or file_id),
                    title=trim(name, 60),
                    document_file_id=file_id,
                    description=f"{file_size} · {doc.get('kind', 'document')}",
                    caption=caption(doc),
                    parse_mode=ParseMode.HTML,
                )
            )

        if not results:
            return await q.answer(
                results=[],
                is_personal=True,
                cache_time=5,
                switch_pm_text="No sendable files found",
                switch_pm_parameter="start",
            )

        pages = max(1, (total + Config.PER_PAGE - 1) // Config.PER_PAGE)
        page = offset // Config.PER_PAGE
        next_offset = (
            str(offset + Config.PER_PAGE)
            if offset + Config.PER_PAGE < total else ""
        )

        await q.answer(
            results=results,
            next_offset=next_offset,
            is_personal=True,
            cache_time=5,
            switch_pm_text=f"📁 Results - {total} · page {page + 1}/{pages}",
            switch_pm_parameter="start",
        )

    except Exception:
        log.exception("Inline search failed for query=%r user_id=%s", query, getattr(q.from_user, "id", None))
        try:
            await q.answer(
                results=[],
                cache_time=0,
                switch_pm_text="Search error — try again",
                switch_pm_parameter="start",
            )
        except Exception:
            log.exception("Could not send inline search error response")
