import html
import math
import re
import time

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config

_QUALITY = re.compile(r"\b(2160p|1080p|720p|480p|360p|hdrip|webrip|web-dl|bluray|blu-ray|camrip|predvd|hdts)\b", re.I)
_SEASON = re.compile(r"\bs(eason)?\s*0*(\d{1,2})\b", re.I)
_EPISODE = re.compile(r"\be(pisode)?\s*0*(\d{1,4})\b|\bep\.?\s*0*(\d{1,4})\b", re.I)


def size(n: int | None) -> str:
    if not n:
        return "—"
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < step or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= step
    return "—"


def runtime(sec: int) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m" if h else f"{m}m {s}s"


def esc(t: str) -> str:
    return html.escape(t or "")


def trim(t: str, n: int = 60) -> str:
    t = (t or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def tokens(name: str) -> dict:
    q = _QUALITY.search(name or "")
    s = _SEASON.search(name or "")
    e = _EPISODE.search(name or "")
    ep = None
    if e:
        ep = e.group(2) or e.group(3)
    return {
        "quality": q.group(1).upper() if q else None,
        "season": s.group(2) if s else None,
        "episode": ep,
    }


def caption(doc: dict) -> str:
    t = tokens(doc.get("name", ""))
    lines = [f"<b>{esc(trim(doc.get('name'), 80))}</b>", "┄" * 12]
    lines.append(f"◦ <b>Size</b> — <code>{size(doc.get('size'))}</code>")
    if t["quality"]:
        lines.append(f"◦ <b>Quality</b> — <code>{t['quality']}</code>")
    if t["season"]:
        lines.append(f"◦ <b>Season</b> — <code>{t['season']}</code>")
    if t["episode"]:
        lines.append(f"◦ <b>Episode</b> — <code>{t['episode']}</code>")
    lines.append(f"◦ <b>Source</b> — {esc(doc.get('channel_title') or 'channel')}")
    return "\n".join(lines)


def result_keyboard(
    docs: list[dict],
    query: str,
    page: int,
    total: int,
    bot_username: str | None = None,
) -> InlineKeyboardMarkup:
    rows = []
    for d in docs:
        name = trim(d.get("name") or "Unnamed file", 60)
        if bot_username:
            url = f"https://t.me/{bot_username}?start=file_{d['_id']}"
            rows.append([InlineKeyboardButton(name, url=url)])
        else:
            rows.append([InlineKeyboardButton(name, callback_data=f"send:{d['_id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("‹ Prev", callback_data=f"page:{page - 1}:{query}"))
    pages = max(1, math.ceil(total / Config.PER_PAGE))
    nav.append(InlineKeyboardButton(f"{page + 1}/{pages}", callback_data="noop"))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton("Next ›", callback_data=f"page:{page + 1}:{query}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton("✕ Close", callback_data="close")])
    return InlineKeyboardMarkup(rows)


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Search a title", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("How to use", callback_data="help")],
    ])
