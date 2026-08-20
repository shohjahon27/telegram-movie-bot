from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

import texts

log = logging.getLogger("bot.user")


def subscription_keyboard(channels_list, pending_movie_number: int = 0) -> InlineKeyboardMarkup:
    """Create keyboard with buttons for all mandatory channels."""
    keyboard = []
    
    # Convert single dict to list
    if isinstance(channels_list, dict):
        channels_list = [channels_list]
    
    # If channels_list is None or empty, return basic keyboard
    if not channels_list:
        keyboard.append([InlineKeyboardButton(text="📢 Kanal", url="https://t.me")])
    else:
        # Add join button for each channel
        for i, channel in enumerate(channels_list, 1):
            # Ensure channel is a dict
            if not isinstance(channel, dict):
                log.error(f"Channel is not dict: {type(channel)} - {channel}")
                continue
            
            # Get username or invite link
            username = channel.get("username", "").replace("@", "").strip()
            invite_link = channel.get("invite_link", "")
            channel_title = channel.get("title", "") or username or f"Channel {i}"
            
            # Determine URL
            if username and username != "|":
                join_url = f"https://t.me/{username}"
            elif invite_link and invite_link != "|":
                join_url = invite_link
            else:
                join_url = "https://t.me"
            
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