import time

from motor.motor_asyncio import AsyncIOMotorClient

from config import Config

client = AsyncIOMotorClient(Config.DATABASE_URI)
db = client[Config.DATABASE_NAME]

files = db.files
users = db.users
chats = db.chats
banned = db.banned


async def ensure_indexes():
    await files.create_index("name_lower")
    await files.create_index([("size", -1)])
    await files.create_index("created_at")


async def save_file(doc: dict) -> bool:
    doc["created_at"] = time.time()
    doc["name_lower"] = (doc.get("name") or "").lower()
    try:
        await files.insert_one(doc)
        return True
    except Exception:
        return False  # duplicate _id = pehle se indexed


async def get_file(uid: str) -> dict | None:
    return await files.find_one({"_id": uid})


async def search(query: str, offset: int = 0, limit: int = 8) -> tuple[list[dict], int]:
    rx = {"name_lower": {"$regex": query.lower().strip(), "$options": "i"}}
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
    await users.update_one({"_id": uid}, {"$set": {"name": name}, "$setOnInsert": {"joined": time.time()}}, upsert=True)


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
