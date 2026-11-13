import os

from dotenv import load_dotenv

load_dotenv()


def _ids(key: str) -> set[int]:
    raw = os.environ.get(key, "").replace(",", " ")
    return {int(x) for x in raw.split() if x.lstrip("-").isdigit()}


def _bool(key: str, default: bool = False) -> bool:
    v = os.environ.get(key)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    API_ID = int(os.environ["API_ID"])
    API_HASH = os.environ["API_HASH"]
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    USER_SESSION_STRING = os.environ.get("USER_SESSION_STRING", "").strip()

    DATABASE_URI = os.environ["DATABASE_URI"]
    DATABASE_NAME = os.environ.get("DATABASE_NAME", "").strip()

    ADMINS = _ids("ADMINS")
    DB_CHANNELS = _ids("DB_CHANNELS")
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL") or 0)
    FORCE_SUB = _ids("FORCE_SUB")

    BOT_USERNAME = os.environ.get("BOT_USERNAME", "").lstrip("@")
    START_PIC = os.environ.get("START_PIC", "")

    PROTECT = _bool("PROTECT", True)
    AUTO_DELETE = max(0, int(os.environ.get("AUTO_DELETE_SEC", "600") or 0))
    PER_PAGE = max(1, min(20, int(os.environ.get("RESULTS_PER_PAGE", "8") or 8)))
    MAX_RESULTS = 300
