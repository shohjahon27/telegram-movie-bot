"""MongoDB data access. No migration files: collections and indexes are
created/ensured automatically on startup (see init_indexes). Documents use
Telegram IDs as _id where natural (users, admins, channels) so upserts are
a single atomic replace_one(..., upsert=True) with no separate uniqueness
bookkeeping needed.
"""
from datetime import datetime, timezone
import ssl
import certifi

from motor.motor_asyncio import AsyncIOMotorClient

import config

# SSL workaround for macOS
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Create client with SSL settings
client = AsyncIOMotorClient(
    config.MONGO_URI,
    tls=True,
    tlsAllowInvalidCertificates=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=30000,
    connectTimeoutMS=30000,
    socketTimeoutMS=30000,
    retryWrites=True,
    w='majority'
)

db = client[config.MONGO_DB_NAME]

users = db.users
movies = db.movies
admins = db.admins
channels = db.channels
requests = db.requests
broadcasts = db.broadcasts


def now():
    return datetime.now(timezone.utc)


async def init_indexes():
    """Called once at startup. Safe to call every boot (create_index is
    idempotent). This replaces what a migrations/ directory would do in a
    SQL project."""
    try:
        # Test connection first
        await client.admin.command('ping')
        print("✅ MongoDB connection verified")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        raise

    # Create indexes with individual error handling
    indexes = [
        (movies, "movie_number", True),
        (movies, "title", False),
        (movies, "is_active", False),
        (requests, "user_id", False),
        (requests, "movie_number", False),
        (requests, "requested_at", False),
        (users, "created_at", False),
    ]
    
    for collection, field, unique in indexes:
        try:
            await collection.create_index(field, unique=unique)
            print(f"✅ Index created: {collection.name}.{field}")
        except Exception as e:
            print(f"⚠️ Index {collection.name}.{field}: {e}")


# --- users -------------------------------------------------------------------

async def upsert_user(telegram_id: int, username: str, first_name: str,
                       last_name: str, language_code: str) -> dict:
    doc = {
        "username": username or "",
        "first_name": first_name or "",
        "last_name": last_name or "",
        "language_code": language_code or "",
        "last_seen_at": now(),
    }
    await users.update_one(
        {"_id": telegram_id},
        {"$set": doc, "$setOnInsert": {
            "_id": telegram_id, "is_subscribed": False, "is_banned": False, "created_at": now(),
        }},
        upsert=True,
    )
    return await users.find_one({"_id": telegram_id})


async def get_user(telegram_id: int) -> dict | None:
    return await users.find_one({"_id": telegram_id})


async def set_user_subscribed(telegram_id: int, subscribed: bool):
    await users.update_one({"_id": telegram_id}, {"$set": {"is_subscribed": subscribed}})


async def set_user_banned(telegram_id: int, banned: bool):
    await users.update_one({"_id": telegram_id}, {"$set": {"is_banned": banned}})


async def list_users_paginated(page: int, page_size: int) -> tuple[list[dict], int]:
    total = await users.count_documents({})
    cursor = users.find({}).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    return await cursor.to_list(length=page_size), total


async def list_active_user_ids() -> list[int]:
    cursor = users.find({"is_banned": {"$ne": True}}, {"_id": 1})
    return [doc["_id"] async for doc in cursor]


async def count_users_stats() -> dict:
    total = await users.count_documents({})
    subscribed = await users.count_documents({"is_subscribed": True})
    banned = await users.count_documents({"is_banned": True})
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = await users.count_documents({"created_at": {"$gte": today_start}})
    return {"total": total, "subscribed": subscribed, "banned": banned, "new_today": new_today}


# --- movies --------------------------------------------------------------------

async def get_movie_by_number(movie_number: int, active_only: bool = True) -> dict | None:
    query = {"movie_number": movie_number}
    if active_only:
        query["is_active"] = True
    return await movies.find_one(query)


async def create_movie(movie_number: int, title: str, year, genre: str,
                        description: str, file_id: str, file_type: str,
                        thumbnail_file_id: str, created_by: int):
    if await movies.find_one({"movie_number": movie_number}):
        return None  # caller checks for None to detect duplicate
    doc = {
        "movie_number": movie_number, "title": title, "year": year, "genre": genre or "",
        "description": description or "", "file_id": file_id, "file_type": file_type,
        "thumbnail_file_id": thumbnail_file_id or "", "is_active": True, "view_count": 0,
        "created_by": created_by, "created_at": now(), "updated_at": now(),
    }
    result = await movies.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def update_movie(movie_number: int, fields: dict):
    fields["updated_at"] = now()
    await movies.update_one({"movie_number": movie_number}, {"$set": fields})
    return await movies.find_one({"movie_number": movie_number})


async def delete_movie(movie_number: int) -> bool:
    result = await movies.delete_one({"movie_number": movie_number})
    return result.deleted_count > 0


async def increment_view_count(movie_number: int):
    await movies.update_one({"movie_number": movie_number}, {"$inc": {"view_count": 1}})


async def search_movies(query: str, page: int, page_size: int):
    filter_ = {"is_active": True, "title": {"$regex": query, "$options": "i"}}
    total = await movies.count_documents(filter_)
    cursor = movies.find(filter_).sort("movie_number", 1).skip((page - 1) * page_size).limit(page_size)
    return await cursor.to_list(length=page_size), total


async def list_movies_paginated(page: int, page_size: int, active_only: bool = False):
    filter_ = {"is_active": True} if active_only else {}
    total = await movies.count_documents(filter_)
    cursor = movies.find(filter_).sort("movie_number", 1).skip((page - 1) * page_size).limit(page_size)
    return await cursor.to_list(length=page_size), total


async def count_movies_stats() -> dict:
    total = await movies.count_documents({})
    active = await movies.count_documents({"is_active": True})
    return {"total": total, "active": active}


# --- admins --------------------------------------------------------------------

async def get_admin(telegram_id: int) -> dict | None:
    return await admins.find_one({"_id": telegram_id, "is_active": True})


async def create_admin(telegram_id: int, username: str, role: str, created_by):
    doc = {
        "_id": telegram_id, "username": username or "", "role": role, "is_active": True,
        "created_at": now(), "created_by": created_by,
    }
    await admins.replace_one({"_id": telegram_id}, doc, upsert=True)
    return await admins.find_one({"_id": telegram_id})


async def deactivate_admin(telegram_id: int) -> bool:
    result = await admins.update_one({"_id": telegram_id}, {"$set": {"is_active": False}})
    return result.modified_count > 0


async def list_admins() -> list[dict]:
    return await admins.find({}).sort("created_at", 1).to_list(length=None)


async def count_active_admins() -> int:
    return await admins.count_documents({"is_active": True})


# --- channels --------------------------------------------------------------------

async def get_mandatory_channel() -> dict | None:
    return await channels.find_one({"is_mandatory": True, "is_active": True}, sort=[("_id", -1)])


async def set_channel(chat_id: int, username: str, title: str, invite_link: str) -> dict:
    doc = {
        "username": username or "", "title": title or "", "invite_link": invite_link or "",
        "is_mandatory": True, "is_active": True, "updated_at": now(),
    }
    await channels.update_one(
        {"_id": chat_id},
        {"$set": doc, "$setOnInsert": {"_id": chat_id, "created_at": now()}},
        upsert=True,
    )
    return await channels.find_one({"_id": chat_id})


# --- requests (for stats) ----------------------------------------------------

async def log_request(user_id: int, movie_number: int, movie_id, source: str, fulfilled: bool):
    await requests.insert_one({
        "user_id": user_id, "movie_number": movie_number, "movie_id": movie_id,
        "source": source, "fulfilled": fulfilled, "requested_at": now(),
    })


async def count_requests_stats() -> dict:
    total = await requests.count_documents({})
    fulfilled = await requests.count_documents({"fulfilled": True})
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today = await requests.count_documents({"requested_at": {"$gte": today_start}})
    return {"total": total, "fulfilled": fulfilled, "today": today}


async def top_requested_movies(limit: int = 5) -> list[dict]:
    pipeline = [
        {"$group": {"_id": "$movie_number", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    results = await requests.aggregate(pipeline).to_list(length=limit)
    out = []
    for r in results:
        movie = await movies.find_one({"movie_number": r["_id"]})
        out.append({"movie_number": r["_id"], "title": movie["title"] if movie else "(deleted)", "count": r["count"]})
    return out


# --- broadcasts ------------------------------------------------------------------

async def create_broadcast(admin_id: int, text: str, targeted: int) -> str:
    result = await broadcasts.insert_one({
        "admin_id": admin_id, "message_text": text, "total_targeted": targeted,
        "total_sent": 0, "total_failed": 0, "status": "running", "created_at": now(),
    })
    return str(result.inserted_id)


async def finish_broadcast(broadcast_id: str, sent: int, failed: int, status: str):
    from bson import ObjectId
    await broadcasts.update_one(
        {"_id": ObjectId(broadcast_id)},
        {"$set": {"total_sent": sent, "total_failed": failed, "status": status, "finished_at": now()}},
    )