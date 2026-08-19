from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import texts


def subscription_keyboard(channel, pending_movie_number: int = 0) -> InlineKeyboardMarkup:
    # Defensive: `channel` must be the MongoDB document (a dict). If it's
    # anything else — a stale/mismatched deploy, bad data, etc. — fail
    # loudly in the logs but still hand back a usable keyboard instead of
    # crashing the handler and leaving the user with no response at all.
    if not isinstance(channel, dict):
        import logging
        logging.getLogger("bot.keyboards").error(
            "subscription_keyboard got non-dict channel: %r (type=%s)", channel, type(channel)
        )
        channel = {}

    join_url = channel.get("invite_link") or ""
    if not join_url and channel.get("username"):
        join_url = f"https://t.me/{channel['username']}"

    verify_data = "verify_sub"
    if pending_movie_number:
        verify_data = f"verify_sub:{pending_movie_number}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_JOIN_CHANNEL, url=join_url or "https://t.me")],
        [InlineKeyboardButton(text=texts.BTN_VERIFY, callback_data=verify_data)],
    ])


def pagination_keyboard(prefix: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    row = []
    if page > 1:
        row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"{prefix}:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[row])