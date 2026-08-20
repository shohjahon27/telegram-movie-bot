import logging

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import texts

log = logging.getLogger("bot.keyboards")


def subscription_keyboard(channels: list[dict], pending_movie_number: int = 0) -> InlineKeyboardMarkup:
    """One join button per mandatory channel, plus a single Verify button
    that re-checks membership in ALL of them."""
    keyboard = []

    for i, channel in enumerate(channels, 1):
        if not isinstance(channel, dict):
            # Defensive: a caller passing a single dict instead of a list
            # would land here -- log loudly instead of crashing the handler.
            log.error("subscription_keyboard got a non-dict channel entry: %r", channel)
            continue

        if channel.get("username"):
            username = channel["username"].replace("@", "").strip()
            join_url = f"https://t.me/{username}"
        elif channel.get("invite_link"):
            join_url = channel["invite_link"]
        else:
            join_url = "https://t.me"

        channel_title = channel.get("title") or f"Channel {i}"
        keyboard.append([InlineKeyboardButton(text=f"📢 {channel_title}", url=join_url)])

    verify_data = "verify_sub"
    if pending_movie_number:
        verify_data = f"verify_sub:{pending_movie_number}"

    keyboard.append([InlineKeyboardButton(text=texts.BTN_VERIFY, callback_data=verify_data)])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def pagination_keyboard(prefix: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    row = []
    if page > 1:
        row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"{prefix}:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[row])
