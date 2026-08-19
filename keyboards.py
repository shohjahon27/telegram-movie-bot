from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import texts


def subscription_keyboard(channels: list[dict], pending_movie_number: int = 0) -> InlineKeyboardMarkup:
    """Create keyboard with multiple channel join buttons."""
    keyboard = []
    
    # Add join button for each channel
    for i, channel in enumerate(channels, 1):
        if channel.get("username"):
            username = channel["username"].replace("@", "").strip()
            join_url = f"https://t.me/{username}"
        elif channel.get("invite_link"):
            join_url = channel["invite_link"]
        else:
            join_url = "https://t.me"
        
        channel_title = channel.get("title") or f"Channel {i}"
        button_text = f"📢 {channel_title}"
        
        keyboard.append([InlineKeyboardButton(text=button_text, url=join_url)])
    
    # Add verify button
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