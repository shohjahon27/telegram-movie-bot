from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

import texts

log = logging.getLogger("bot.user")

def subscription_keyboard(channel: dict, pending_movie_number: int = 0) -> InlineKeyboardMarkup:
    join_url = ""
    username = channel.get("username", "").replace("@", "").strip()
    
    if username and username != "|" and username != "":
        join_url = f"https://t.me/{username}"
        log.info(f"Using username link: {join_url}")
    elif channel.get("invite_link"):
        join_url = channel["invite_link"]
        log.info(f"Using invite link: {join_url}")
    else:
        # Fallback - log error
        log.error(f"No valid username or invite link in channel: {channel}")
        join_url = "https://t.me"
    
    verify_data = "verify_sub"
    if pending_movie_number:
        verify_data = f"verify_sub:{pending_movie_number}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_JOIN_CHANNEL, url=join_url)],
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