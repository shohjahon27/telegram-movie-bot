import asyncio
import logging

from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

import database as db
import texts
from handlers.user import parse_movie_number

router = Router()
log = logging.getLogger("bot.admin")

BROADCAST_CONCURRENCY = 5
BROADCAST_DELAY_SECONDS = 0.04  # ~25 messages/sec, under Telegram's global cap


async def require_admin(message: Message) -> dict | None:
    """Returns the admin doc if authorized, else sends a rejection and
    returns None."""
    if message.from_user is None:
        return None
    admin = await db.get_admin(message.from_user.id)
    if admin is None:
        await message.answer(texts.NOT_ADMIN)
        return None
    return admin


async def require_super_admin(message: Message) -> dict | None:
    admin = await require_admin(message)
    if admin is None:
        return None
    if admin.get("role") != "super_admin":
        await message.answer(texts.SUPER_ADMIN_ONLY)
        return None
    return admin


def extract_file(message: Message) -> tuple[str, str, str] | None:
    """Pulls (file_id, file_type, thumbnail_file_id) from an attached
    video/document. Returns None if nothing is attached."""
    if message.video:
        thumb = message.video.thumbnail.file_id if message.video.thumbnail else ""
        return message.video.file_id, "video", thumb
    if message.document:
        thumb = message.document.thumbnail.file_id if message.document.thumbnail else ""
        return message.document.file_id, "document", thumb
    return None


@router.message(Command("addmovie"))
async def cmd_addmovie(message: Message, command: CommandObject):
    """Usage: attach a video/document to a message with caption:
    /addmovie 1025|Movie Title|2024|Action|Short description
    """
    if await require_admin(message) is None:
        return

    file = extract_file(message)
    if file is None:
        await message.answer(
            "⚠️ Iltimos, videoni/faylni shu buyruq bilan birga yuboring.\n"
            "Please attach the video/document file to this command's caption.\n\n"
            "Format: /addmovie <number>|<title>|<year>|<genre>|<description>"
        )
        return
    file_id, file_type, thumb_id = file

    args = command.args or ""
    fields = args.split("|", 4)
    if len(fields) < 2:
        await message.answer("Format: /addmovie <number>|<title>|<year>|<genre>|<description>")
        return

    movie_number = parse_movie_number(fields[0].strip())
    if movie_number is None:
        await message.answer("⚠️ Noto'g'ri raqam / Invalid movie number.")
        return
    title = fields[1].strip()
    if not title or len(title) > 200:
        await message.answer("⚠️ Sarlavha 1-200 belgidan iborat bo'lishi kerak / Title must be 1-200 characters.")
        return

    year = None
    if len(fields) > 2 and fields[2].strip().isdigit():
        year = int(fields[2].strip())
    genre = fields[3].strip() if len(fields) > 3 else ""
    description = fields[4].strip() if len(fields) > 4 else ""

    created = await db.create_movie(
        movie_number, title, year, genre, description, file_id, file_type, thumb_id,
        message.from_user.id,
    )
    if created is None:
        await message.answer(f"⚠️ #{movie_number} raqami band. / Movie number {movie_number} is already taken.")
        return

    await message.answer(f"✅ Film qo'shildi / Movie added: #{movie_number} — {title}")


@router.message(Command("editmovie"))
async def cmd_editmovie(message: Message, command: CommandObject):
    """Usage: /editmovie <number> title=New Title;year=2024;genre=Drama;active=true
    Optionally attach a new video/document to replace the file."""
    if await require_admin(message) is None:
        return

    args = (command.args or "").strip()
    parts = args.split(" ", 1)
    if not parts or not parts[0]:
        await message.answer("Format: /editmovie <number> title=New Title;year=2024;genre=Drama;active=true")
        return

    movie_number = parse_movie_number(parts[0])
    if movie_number is None:
        await message.answer("⚠️ Noto'g'ri raqam / Invalid movie number.")
        return

    existing = await db.get_movie_by_number(movie_number, active_only=False)
    if existing is None:
        await message.answer(texts.MOVIE_NOT_FOUND)
        return

    fields = {}
    if len(parts) == 2:
        for kv in parts[1].split(";"):
            kv = kv.strip()
            if "=" not in kv:
                continue
            key, val = kv.split("=", 1)
            key, val = key.strip(), val.strip()
            if key == "title" and val:
                fields["title"] = val
            elif key == "year" and val.isdigit():
                fields["year"] = int(val)
            elif key == "genre":
                fields["genre"] = val
            elif key == "description":
                fields["description"] = val
            elif key == "active":
                fields["is_active"] = val.lower() in ("true", "1")

    file = extract_file(message)
    if file:
        fields["file_id"], fields["file_type"], thumb = file
        if thumb:
            fields["thumbnail_file_id"] = thumb

    updated = await db.update_movie(movie_number, fields)
    await message.answer(f"✅ Yangilandi / Updated: #{movie_number} — {updated['title']}")

    from ratelimit import invalidate_movie_cache
    invalidate_movie_cache(movie_number)


@router.message(Command("deletemovie"))
async def cmd_deletemovie(message: Message, command: CommandObject):
    if await require_admin(message) is None:
        return

    movie_number = parse_movie_number(command.args or "")
    if movie_number is None:
        await message.answer("Format: /deletemovie <number>")
        return

    deleted = await db.delete_movie(movie_number)
    if not deleted:
        await message.answer(texts.MOVIE_NOT_FOUND)
        return

    from ratelimit import invalidate_movie_cache
    invalidate_movie_cache(movie_number)
    await message.answer(f"🗑 O'chirildi / Deleted: #{movie_number}")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, command: CommandObject, bot: Bot):
    if await require_admin(message) is None:
        return

    text = (command.args or "").strip()
    if not text:
        await message.answer("Format: /broadcast <message text>")
        return
    if len(text) > 4096:
        await message.answer("⚠️ Xabar juda uzun (max 4096) / Message too long (max 4096 chars).")
        return

    user_ids = await db.list_active_user_ids()
    broadcast_id = await db.create_broadcast(message.from_user.id, text, len(user_ids))

    await message.answer(f"📤 Yuborilmoqda ({len(user_ids)} ta foydalanuvchi)... / Sending to {len(user_ids)} users, this runs in the background.")

    asyncio.create_task(_run_broadcast(bot, broadcast_id, user_ids, text, message.chat.id))


async def _run_broadcast(bot: Bot, broadcast_id: str, user_ids: list[int], text: str, notify_chat_id: int):
    sent = failed = 0
    semaphore = asyncio.Semaphore(BROADCAST_CONCURRENCY)

    async def send_one(uid: int):
        nonlocal sent, failed
        async with semaphore:
            try:
                await bot.send_message(uid, text)
                sent += 1
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                try:
                    await bot.send_message(uid, text)
                    sent += 1
                except TelegramAPIError:
                    failed += 1
            except TelegramAPIError:
                failed += 1
            await asyncio.sleep(BROADCAST_DELAY_SECONDS)

    await asyncio.gather(*(send_one(uid) for uid in user_ids))

    await db.finish_broadcast(broadcast_id, sent, failed, "completed")
    try:
        await bot.send_message(notify_chat_id, f"✅ Broadcast yakunlandi / completed: {sent} sent, {failed} failed.")
    except TelegramAPIError:
        pass


@router.message(Command("users"))
async def cmd_users(message: Message, command: CommandObject):
    if await require_admin(message) is None:
        return

    page = 1
    if (command.args or "").strip().isdigit():
        page = max(1, int(command.args.strip()))

    users, total = await db.list_users_paginated(page, 15)
    lines = [f"👥 Foydalanuvchilar / Users ({total} jami/total)\n"]
    for u in users:
        status = "🚫" if u.get("is_banned") else "✅"
        lines.append(f"{status} {u['_id']} @{u.get('username', '')} {u.get('first_name', '')} {u.get('last_name', '')}")
    await message.answer("\n".join(lines))


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if await require_admin(message) is None:
        return

    users_stats = await db.count_users_stats()
    movies_stats = await db.count_movies_stats()
    requests_stats = await db.count_requests_stats()
    top = await db.top_requested_movies(5)

    lines = ["📊 Statistika / Stats\n"]
    lines.append(f"Foydalanuvchilar / Users: {users_stats['total']} "
                 f"(obuna: {users_stats['subscribed']}, bugun yangi: {users_stats['new_today']}, "
                 f"bloklangan: {users_stats['banned']})")
    lines.append(f"Filmlar / Movies: {movies_stats['total']} (faol: {movies_stats['active']})")
    lines.append(f"So'rovlar / Requests: {requests_stats['total']} "
                 f"(bugun: {requests_stats['today']}, bajarilgan: {requests_stats['fulfilled']})\n")
    lines.append("🔥 Ko'p so'ralganlar / Top requested:")
    for t in top:
        lines.append(f"#{t['movie_number']} {t['title']} — {t['count']}")

    await message.answer("\n".join(lines))


@router.message(Command("setchannel"))
async def cmd_setchannel(message: Message, command: CommandObject, bot: Bot):
    if await require_super_admin(message) is None:
        return

    parts = (command.args or "").split()
    if not parts:
        await message.answer("Format: /setchannel <chat_id> [@username_or_invite_link]")
        return

    try:
        chat_id = int(parts[0])
    except ValueError:
        await message.answer("⚠️ chat_id butun son bo'lishi kerak / chat_id must be a number.")
        return

    username, invite_link = "", ""
    if len(parts) > 1:
        v = parts[1]
        if v.startswith("@"):
            username = v.lstrip("@")
        else:
            invite_link = v

    title = ""
    try:
        chat = await bot.get_chat(chat_id)
        title = chat.title or ""
    except TelegramAPIError as e:
        log.warning("could not fetch chat info for %s: %s", chat_id, e)

    channel = await db.set_channel(chat_id, username, title, invite_link)
    await message.answer(f"✅ Kanal o'rnatildi / Channel set: {channel['title']} ({channel['_id']})")


@router.message(Command("addadmin"))
async def cmd_addadmin(message: Message, command: CommandObject):
    if await require_super_admin(message) is None:
        return

    raw = (command.args or "").strip()
    if not raw.isdigit():
        await message.answer("Format: /addadmin <telegram_user_id>")
        return

    new_admin_id = int(raw)
    admin = await db.create_admin(new_admin_id, "", "admin", created_by=message.from_user.id)
    await message.answer(f"✅ Admin qo'shildi / Admin added: {admin['_id']}")


@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject):
    if await require_admin(message) is None:
        return
    raw = (command.args or "").strip()
    if not raw.isdigit():
        await message.answer("Format: /ban <telegram_user_id>")
        return
    await db.set_user_banned(int(raw), True)
    await message.answer(f"🚫 Bloklandi / Banned: {raw}")


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject):
    if await require_admin(message) is None:
        return
    raw = (command.args or "").strip()
    if not raw.isdigit():
        await message.answer("Format: /unban <telegram_user_id>")
        return
    await db.set_user_banned(int(raw), False)
    await message.answer(f"✅ Blokdan chiqarildi / Unbanned: {raw}")
