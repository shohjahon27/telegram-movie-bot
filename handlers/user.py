import logging

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError

import config
import database as db
import keyboards
import ratelimit
import texts

router = Router()
log = logging.getLogger("bot.user")

VALID_MEMBER_STATUSES = {
    ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED,
}


def parse_movie_number(raw: str) -> int | None:
    """Validates and parses a movie number from user input (command arg,
    deep-link payload, or plain text). Returns None if invalid."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw.lstrip("-").isdigit():
        return None
    n = int(raw)
    if n <= 0 or n > 999_999:
        return None
    return n


async def is_subscribed(bot: Bot, telegram_id: int) -> bool:
    """Checks channel membership using username instead of ID."""
    channel = await db.get_mandatory_channel()
    if channel is None:
        return True

    cached = ratelimit.get_cached_subscription(telegram_id)
    if cached is not None:
        return cached

    try:
        # Use username instead of ID if available
        if channel.get("username"):
            chat_id = f"@{channel['username']}"
        else:
            chat_id = channel["_id"]
        
        log.info(f"Checking membership in chat: {chat_id}")
        member = await bot.get_chat_member(chat_id=chat_id, user_id=telegram_id)
        log.info(f"Member status: {member.status}")
        
    except TelegramAPIError as e:
        log.warning("get_chat_member failed: %s", e)
        return False

    subscribed = member.status in VALID_MEMBER_STATUSES
    ratelimit.set_cached_subscription(telegram_id, subscribed, config.SUBSCRIPTION_CACHE_SECONDS)
    return subscribed


async def upsert_from_message(message: Message) -> dict | None:
    if message.from_user is None:
        return None
    u = message.from_user
    return await db.upsert_user(u.id, u.username or "", u.first_name or "", u.last_name or "", u.language_code or "")


async def guard(message_or_cb, user_doc: dict | None, action: str = "") -> bool:
    """Shared abuse-protection: ban check, rate limit, duplicate suppression.
    Returns False if the caller should stop processing (a rejection message
    has already been sent, if warranted)."""
    telegram_id = message_or_cb.from_user.id
    chat = message_or_cb.message.chat if isinstance(message_or_cb, CallbackQuery) else message_or_cb.chat
    if chat is None:
        return False

    if user_doc and user_doc.get("is_banned"):
        await message_or_cb.bot.send_message(chat.id, texts.BANNED)
        return False

    if not ratelimit.allow(telegram_id, config.RATE_LIMIT_PER_MINUTE):
        await message_or_cb.bot.send_message(chat.id, texts.RATE_LIMITED)
        return False

    if action and ratelimit.is_duplicate(telegram_id, action, config.DUPLICATE_WINDOW_SECONDS):
        return False  # silent drop — double-tap/redelivery, not a real user action

    return True


async def check_subscription_or_prompt(bot: Bot, chat_id: int, telegram_id: int, pending_movie_number: int = 0) -> bool:
    """Returns True if verified. Otherwise sends the Join/Verify prompt and
    returns False."""
    if await is_subscribed(bot, telegram_id):
        return True

    channel = await db.get_mandatory_channel()
    if channel is None:
        return True  # nothing configured to gate on

    kb = keyboards.subscription_keyboard(channel, pending_movie_number)
    await bot.send_message(chat_id, texts.NOT_SUBSCRIBED, reply_markup=kb)
    return False


async def deliver_movie(bot: Bot, chat_id: int, telegram_id: int, movie_number: int, source: str):
    """Shared 'subscription already confirmed' delivery path used by
    /movie, /start deep links, and verify-then-deliver."""
    movie = ratelimit.get_cached_movie(movie_number)
    if movie is None:
        movie = await db.get_movie_by_number(movie_number, active_only=True)
        if movie:
            ratelimit.set_cached_movie(movie_number, movie, config.MOVIE_CACHE_SECONDS)

    if movie is None:
        await db.log_request(telegram_id, movie_number, None, source, False)
        await bot.send_message(chat_id, texts.MOVIE_NOT_FOUND)
        return

    caption = f"🎬 {movie['title']}"
    if movie.get("year"):
        caption += f" ({movie['year']})"
    if movie.get("genre"):
        caption += f"\n🎭 {movie['genre']}"
    if movie.get("description"):
        caption += f"\n\n{movie['description']}"

    try:
        if movie.get("file_type") == "document":
            await bot.send_document(chat_id, document=movie["file_id"], caption=caption)
        else:
            # Note: Telegram's sendVideo `thumbnail` param only accepts a
            # freshly-uploaded file, not a reused file_id — so we don't pass
            # one here. Telegram auto-generates a thumbnail server-side when
            # resending a video that already exists on its servers.
            await bot.send_video(chat_id, video=movie["file_id"], caption=caption)
    except TelegramAPIError as e:
        log.error("failed to send movie %s to %s: %s", movie_number, chat_id, e)
        await db.log_request(telegram_id, movie_number, movie["_id"], source, False)
        await bot.send_message(chat_id, texts.GENERIC_ERROR)
        return

    await db.log_request(telegram_id, movie_number, movie["_id"], source, True)
    await db.increment_view_count(movie_number)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot: Bot):
    user_doc = await upsert_from_message(message)
    if not await guard(message, user_doc):
        return

    pending_movie_number = parse_movie_number(command.args or "") or 0

    if not await check_subscription_or_prompt(bot, message.chat.id, message.from_user.id, pending_movie_number):
        return

    await db.set_user_subscribed(message.from_user.id, True)

    if pending_movie_number:
        await deliver_movie(bot, message.chat.id, message.from_user.id, pending_movie_number, "deep_link")
        return

    await message.answer(texts.WELCOME + "\n\n" + texts.SEND_MOVIE_NUMBER)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await upsert_from_message(message)
    await message.answer(texts.HELP)


@router.message(Command("movie"))
async def cmd_movie(message: Message, command: CommandObject, bot: Bot):
    user_doc = await upsert_from_message(message)
    if not await guard(message, user_doc):
        return
    if not await check_subscription_or_prompt(bot, message.chat.id, message.from_user.id):
        return

    movie_number = parse_movie_number(command.args or "")
    if movie_number is None:
        await message.answer(texts.INVALID_MOVIE_NUMBER)
        return

    await deliver_movie(bot, message.chat.id, message.from_user.id, movie_number, "command")


@router.message(Command("search"))
async def cmd_search(message: Message, command: CommandObject, bot: Bot):
    user_doc = await upsert_from_message(message)
    if not await guard(message, user_doc):
        return
    if not await check_subscription_or_prompt(bot, message.chat.id, message.from_user.id):
        return

    query = (command.args or "").strip()
    if len(query) < 2:
        await message.answer(texts.SEARCH_USAGE)
        return

    await send_search_page(message.bot, message.chat.id, query, 1)


async def send_search_page(bot: Bot, chat_id: int, query: str, page: int):
    page_size = 8
    results, total = await db.search_movies(query, page, page_size)
    if not results:
        await bot.send_message(chat_id, texts.SEARCH_NO_RESULTS)
        return

    lines = [f'🔎 "{query}" — {total} ta natija / results\n']
    for m in results:
        year = f" ({m['year']})" if m.get("year") else ""
        lines.append(f"#{m['movie_number']} — {m['title']}{year}")
    lines.append("\nOlish uchun /movie <raqam> yuboring. / Send /movie <number> to get it.")

    total_pages = max(1, (total + page_size - 1) // page_size)
    kb = keyboards.pagination_keyboard(f"search:{query}", page, total_pages)
    await bot.send_message(chat_id, "\n".join(lines), reply_markup=kb)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("verify_sub"))
async def cb_verify(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    if callback.message is None:
        return
    user_doc = await db.upsert_user(
        callback.from_user.id, callback.from_user.username or "",
        callback.from_user.first_name or "", callback.from_user.last_name or "",
        callback.from_user.language_code or "",
    )
    if not await guard(callback, user_doc, action="verify_sub"):
        return

    chat_id = callback.message.chat.id
    telegram_id = callback.from_user.id

    ratelimit.invalidate_subscription_cache(telegram_id)

    pending_movie_number = 0
    if ":" in callback.data:
        try:
            pending_movie_number = int(callback.data.split(":", 1)[1])
        except ValueError:
            pending_movie_number = 0

    if not await is_subscribed(bot, telegram_id):
        await bot.send_message(chat_id, texts.STILL_NOT_SUBSCRIBED)
        return

    await db.set_user_subscribed(telegram_id, True)
    await bot.send_message(chat_id, texts.SUBSCRIPTION_VERIFIED)

    if pending_movie_number:
        await deliver_movie(bot, chat_id, telegram_id, pending_movie_number, "deep_link")
    else:
        await bot.send_message(chat_id, texts.SEND_MOVIE_NUMBER)


@router.callback_query(F.data.startswith("search:"))
async def cb_search_page(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    if callback.message is None:
        return
    user_doc = await db.upsert_user(
        callback.from_user.id, callback.from_user.username or "",
        callback.from_user.first_name or "", callback.from_user.last_name or "",
        callback.from_user.language_code or "",
    )
    if not await guard(callback, user_doc):
        return

    rest = callback.data[len("search:"):]
    if ":" not in rest:
        return
    query, page_str = rest.rsplit(":", 1)
    try:
        page = max(1, int(page_str))
    except ValueError:
        page = 1

    await send_search_page(bot, callback.message.chat.id, query, page)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_plain_text(message: Message, bot: Bot):
    """Any plain-text message is treated as a candidate movie number — the
    primary interaction once a user is verified."""
    user_doc = await upsert_from_message(message)
    if not await guard(message, user_doc):
        return
    if not await check_subscription_or_prompt(bot, message.chat.id, message.from_user.id):
        return

    movie_number = parse_movie_number(message.text or "")
    if movie_number is None:
        await message.answer(texts.INVALID_MOVIE_NUMBER)
        return

    await deliver_movie(bot, message.chat.id, message.from_user.id, movie_number, "command")


@router.message(F.text.startswith("/"))
async def handle_unknown_command(message: Message):
    """Catches any command not matched by a more specific handler above
    (including admin-only commands typed by a non-admin, which the admin
    router lets fall through rather than silently eating)."""
    await upsert_from_message(message)
    await message.answer(texts.HELP)
