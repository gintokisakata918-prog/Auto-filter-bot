import time
import logging
import re

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from config import Config

log = logging.getLogger("autofilter.database")
client = AsyncIOMotorClient(Config.DATABASE_URI, serverSelectionTimeoutMS=15000)
db = None
files = users = chats = banned = settings = None


async def _resolve_database():
    configured = Config.DATABASE_NAME.strip() if Config.DATABASE_NAME else ""
    try:
        default_db = client.get_default_database(default=None)
    except Exception:
        default_db = None
    requested = configured or (default_db.name if default_db is not None else "autofilter")
    try:
        names = await client.list_database_names()
        existing = next((name for name in names if name.casefold() == requested.casefold()), None)
        if existing:
            if existing != requested:
                log.info("MongoDB database name matched existing case: %s", existing)
            return existing
    except PyMongoError as exc:
        log.warning("Could not list MongoDB databases; using %s (%s)", requested, exc)
    return requested


async def ensure_indexes():
    global db, files, users, chats, banned, settings
    database_name = await _resolve_database()
    db = client[database_name]
    files, users, chats, banned, settings = db.files, db.users, db.chats, db.banned, db.settings
    await files.create_index("name_lower")
    await files.create_index([("size", -1)])
    await files.create_index("created_at")
    log.info("MongoDB connected · database=%s", database_name)


async def get_setting(key: str, default=None):
    doc = await settings.find_one({"_id": key})
    return doc.get("value", default) if doc else default


async def set_setting(key: str, value):
    await settings.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)


async def save_file(doc: dict) -> bool:
    doc["created_at"] = time.time()
    doc["name_lower"] = (doc.get("name") or "").lower()
    try:
        await files.insert_one(doc)
        return True
    except Exception:
        return False


async def get_file(uid: str) -> dict | None:
    return await files.find_one({"_id": uid})


async def search(query: str, offset: int = 0, limit: int = 8) -> tuple[list[dict], int]:
    # Treat spaces, dots, underscores, hyphens and other separators equally.
    # Example: "Spooky in Love" matches "Spooky.in.Love" and "Spooky_in_Love".
    tokens = re.findall(r"[^\\W_]+", (query or "").lower(), flags=re.UNICODE)
    if not tokens:
        return [], 0
    pattern = r"[\\W_]*".join(re.escape(token) for token in tokens)
    rx = {"name_lower": {"$regex": pattern, "$options": "i"}}
    total = await files.count_documents(rx)
    cursor = files.find(rx).sort("created_at", -1).skip(offset).limit(limit)
    return [d async for d in cursor], total


async def total_files() -> int:
    return await files.count_documents({})


async def total_users() -> int:
    return await users.count_documents({})


async def total_chats() -> int:
    return await chats.count_documents({"enabled": True})


async def add_user(uid: int, name: str):
    await users.update_one(
        {"_id": uid},
        {"$set": {"name": name}, "$setOnInsert": {"joined": time.time()}},
        upsert=True,
    )


async def all_users() -> list[int]:
    return [d["_id"] async for d in users.find({}, {"_id": 1})]


async def all_chats() -> list[int]:
    return [d["_id"] async for d in chats.find({"enabled": True}, {"_id": 1})]


async def set_chat(cid: int, enabled: bool):
    await chats.update_one({"_id": cid}, {"$set": {"enabled": enabled}}, upsert=True)


async def chat_enabled(cid: int) -> bool:
    doc = await chats.find_one({"_id": cid})
    return bool(doc and doc.get("enabled"))


async def ban(uid: int):
    await banned.update_one({"_id": uid}, {"$set": {"at": time.time()}}, upsert=True)


async def unban(uid: int):
    await banned.delete_one({"_id": uid})


async def is_banned(uid: int) -> bool:
    return await banned.count_documents({"_id": uid}) > 0


async def delete_file(uid: str) -> bool:
    return (await files.delete_one({"_id": uid})).deleted_count > 0


async def delete_all() -> int:
    return (await files.delete_many({})).deleted_count
