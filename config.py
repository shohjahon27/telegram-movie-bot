"""Centralized config, loaded from environment variables (.env in local dev).
No secrets are hardcoded — everything here comes from the environment."""
import os
import sys

from dotenv import load_dotenv

load_dotenv()  # no-op if .env doesn't exist; real deployments inject real env vars


def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        print(f"ERROR: required environment variable {key} is not set. "
              f"Copy .env.example to .env and fill it in.", file=sys.stderr)
        sys.exit(1)
    return value


def _parse_admin_ids(raw: str) -> list[int]:
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
            ids.append(int(part))
    return ids


BOT_TOKEN = _require("BOT_TOKEN")
CHANNEL_ID = int(_require("CHANNEL_ID"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").strip().lstrip("@")

SEED_ADMIN_IDS = _parse_admin_ids(os.getenv("SEED_ADMIN_IDS", ""))
if not SEED_ADMIN_IDS:
    print("WARNING: SEED_ADMIN_IDS is empty — no one will have admin access. "
          "Set it in .env and restart.", file=sys.stderr)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "movie_bot")

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
DUPLICATE_WINDOW_SECONDS = float(os.getenv("DUPLICATE_WINDOW_SECONDS", "2"))
SUBSCRIPTION_CACHE_SECONDS = int(os.getenv("SUBSCRIPTION_CACHE_SECONDS", "600"))
MOVIE_CACHE_SECONDS = int(os.getenv("MOVIE_CACHE_SECONDS", "1800"))
