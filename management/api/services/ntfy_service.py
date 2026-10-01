"""
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/api/services/ntfy_service.py

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
"""

import httpx
import logging
import os
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC
from urllib.parse import urlsplit

from api.services.env_file import read_env_value

logger = logging.getLogger(__name__)

# The self-hosted ntfy server runs with auth-default-access deny-all; the
# installer provisions an admin user and an access token (NTFY_TOKEN in .env)
# that the console uses to publish.
HOST_ENV_PATH = "/app/host_project/.env"
LOCAL_NTFY_HOSTS = {"n8n_ntfy", "ntfy"}


def get_ntfy_token() -> Optional[str]:
    """Return the ntfy access token used for publishing, if configured.

    The host .env is read first so a token updated from the console takes
    effect without recreating this container; the environment is the fallback.
    """
    value = None
    try:
        value = read_env_value(HOST_ENV_PATH, "NTFY_TOKEN")
    except Exception:
        value = None
    if not value:
        value = os.environ.get("NTFY_TOKEN")
    value = (value or "").strip()
    return value or None

# Priority level mappings
PRIORITY_NAMES = {
    1: "min",
    2: "low",
    3: "default",
    4: "high",
    5: "urgent"
}

PRIORITY_VALUES = {
    "min": 1,
    "low": 2,
    "default": 3,
    "high": 4,
    "urgent": 5,
    "max": 5
}

# Common emoji shortcodes for quick reference
# Flat list of {shortcode, emoji} for direct display
COMMON_EMOJIS = [
    # Status & Reactions
    {"shortcode": "white_check_mark", "emoji": "✅"},
    {"shortcode": "heavy_check_mark", "emoji": "✔️"},
    {"shortcode": "x", "emoji": "❌"},
    {"shortcode": "warning", "emoji": "⚠️"},
    {"shortcode": "exclamation", "emoji": "❗"},
    {"shortcode": "question", "emoji": "❓"},
    {"shortcode": "bangbang", "emoji": "‼️"},
    {"shortcode": "interrobang", "emoji": "⁉️"},
    {"shortcode": "+1", "emoji": "👍"},
    {"shortcode": "-1", "emoji": "👎"},
    {"shortcode": "ok_hand", "emoji": "👌"},
    {"shortcode": "clap", "emoji": "👏"},
    {"shortcode": "raised_hands", "emoji": "🙌"},
    {"shortcode": "pray", "emoji": "🙏"},
    {"shortcode": "muscle", "emoji": "💪"},
    {"shortcode": "fire", "emoji": "🔥"},
    {"shortcode": "100", "emoji": "💯"},
    {"shortcode": "star", "emoji": "⭐"},
    {"shortcode": "sparkles", "emoji": "✨"},
    {"shortcode": "zap", "emoji": "⚡"},
    {"shortcode": "boom", "emoji": "💥"},
    {"shortcode": "collision", "emoji": "💥"},
    {"shortcode": "tada", "emoji": "🎉"},
    {"shortcode": "confetti_ball", "emoji": "🎊"},
    {"shortcode": "trophy", "emoji": "🏆"},
    {"shortcode": "medal", "emoji": "🏅"},
    {"shortcode": "crown", "emoji": "👑"},
    {"shortcode": "gem", "emoji": "💎"},

    # Faces & Emotions
    {"shortcode": "grinning", "emoji": "😀"},
    {"shortcode": "smile", "emoji": "😄"},
    {"shortcode": "laughing", "emoji": "😆"},
    {"shortcode": "joy", "emoji": "😂"},
    {"shortcode": "rofl", "emoji": "🤣"},
    {"shortcode": "wink", "emoji": "😉"},
    {"shortcode": "blush", "emoji": "😊"},
    {"shortcode": "heart_eyes", "emoji": "😍"},
    {"shortcode": "sunglasses", "emoji": "😎"},
    {"shortcode": "thinking", "emoji": "🤔"},
    {"shortcode": "neutral_face", "emoji": "😐"},
    {"shortcode": "expressionless", "emoji": "😑"},
    {"shortcode": "unamused", "emoji": "😒"},
    {"shortcode": "rolling_eyes", "emoji": "🙄"},
    {"shortcode": "grimacing", "emoji": "😬"},
    {"shortcode": "sweat", "emoji": "😅"},
    {"shortcode": "worried", "emoji": "😟"},
    {"shortcode": "cry", "emoji": "😢"},
    {"shortcode": "sob", "emoji": "😭"},
    {"shortcode": "scream", "emoji": "😱"},
    {"shortcode": "angry", "emoji": "😠"},
    {"shortcode": "rage", "emoji": "😡"},
    {"shortcode": "skull", "emoji": "💀"},
    {"shortcode": "ghost", "emoji": "👻"},
    {"shortcode": "alien", "emoji": "👽"},
    {"shortcode": "robot", "emoji": "🤖"},
    {"shortcode": "poop", "emoji": "💩"},
    {"shortcode": "see_no_evil", "emoji": "🙈"},
    {"shortcode": "hear_no_evil", "emoji": "🙉"},
    {"shortcode": "speak_no_evil", "emoji": "🙊"},

    # Hearts & Love
    {"shortcode": "heart", "emoji": "❤️"},
    {"shortcode": "orange_heart", "emoji": "🧡"},
    {"shortcode": "yellow_heart", "emoji": "💛"},
    {"shortcode": "green_heart", "emoji": "💚"},
    {"shortcode": "blue_heart", "emoji": "💙"},
    {"shortcode": "purple_heart", "emoji": "💜"},
    {"shortcode": "black_heart", "emoji": "🖤"},
    {"shortcode": "white_heart", "emoji": "🤍"},
    {"shortcode": "broken_heart", "emoji": "💔"},
    {"shortcode": "heartbeat", "emoji": "💓"},
    {"shortcode": "heartpulse", "emoji": "💗"},
    {"shortcode": "two_hearts", "emoji": "💕"},
    {"shortcode": "sparkling_heart", "emoji": "💖"},

    # Alerts & Warnings
    {"shortcode": "rotating_light", "emoji": "🚨"},
    {"shortcode": "sos", "emoji": "🆘"},
    {"shortcode": "no_entry", "emoji": "⛔"},
    {"shortcode": "no_entry_sign", "emoji": "🚫"},
    {"shortcode": "stop_sign", "emoji": "🛑"},
    {"shortcode": "radioactive", "emoji": "☢️"},
    {"shortcode": "biohazard", "emoji": "☣️"},
    {"shortcode": "construction", "emoji": "🚧"},
    {"shortcode": "triangular_flag", "emoji": "🚩"},

    # Actions & Controls
    {"shortcode": "rocket", "emoji": "🚀"},
    {"shortcode": "airplane", "emoji": "✈️"},
    {"shortcode": "arrow_forward", "emoji": "▶️"},
    {"shortcode": "arrow_backward", "emoji": "◀️"},
    {"shortcode": "play_or_pause_button", "emoji": "⏯️"},
    {"shortcode": "stop_button", "emoji": "⏹️"},
    {"shortcode": "record_button", "emoji": "⏺️"},
    {"shortcode": "fast_forward", "emoji": "⏩"},
    {"shortcode": "rewind", "emoji": "⏪"},
    {"shortcode": "arrows_counterclockwise", "emoji": "🔄"},
    {"shortcode": "recycle", "emoji": "♻️"},
    {"shortcode": "repeat", "emoji": "🔁"},
    {"shortcode": "twisted_rightwards_arrows", "emoji": "🔀"},
    {"shortcode": "arrow_up", "emoji": "⬆️"},
    {"shortcode": "arrow_down", "emoji": "⬇️"},
    {"shortcode": "arrow_left", "emoji": "⬅️"},
    {"shortcode": "arrow_right", "emoji": "➡️"},
    {"shortcode": "arrow_heading_up", "emoji": "⤴️"},
    {"shortcode": "arrow_heading_down", "emoji": "⤵️"},
    {"shortcode": "leftwards_arrow_with_hook", "emoji": "↩️"},
    {"shortcode": "arrow_right_hook", "emoji": "↪️"},

    # Technology & Devices
    {"shortcode": "computer", "emoji": "💻"},
    {"shortcode": "desktop_computer", "emoji": "🖥️"},
    {"shortcode": "keyboard", "emoji": "⌨️"},
    {"shortcode": "mouse", "emoji": "🖱️"},
    {"shortcode": "printer", "emoji": "🖨️"},
    {"shortcode": "iphone", "emoji": "📱"},
    {"shortcode": "telephone", "emoji": "📞"},
    {"shortcode": "pager", "emoji": "📟"},
    {"shortcode": "fax", "emoji": "📠"},
    {"shortcode": "battery", "emoji": "🔋"},
    {"shortcode": "electric_plug", "emoji": "🔌"},
    {"shortcode": "bulb", "emoji": "💡"},
    {"shortcode": "flashlight", "emoji": "🔦"},
    {"shortcode": "satellite", "emoji": "📡"},
    {"shortcode": "tv", "emoji": "📺"},
    {"shortcode": "radio", "emoji": "📻"},
    {"shortcode": "video_camera", "emoji": "📹"},
    {"shortcode": "camera", "emoji": "📷"},
    {"shortcode": "movie_camera", "emoji": "🎥"},
    {"shortcode": "cd", "emoji": "💿"},
    {"shortcode": "dvd", "emoji": "📀"},
    {"shortcode": "floppy_disk", "emoji": "💾"},
    {"shortcode": "minidisc", "emoji": "💽"},
    {"shortcode": "vhs", "emoji": "📼"},

    # Data & Storage
    {"shortcode": "file_folder", "emoji": "📁"},
    {"shortcode": "open_file_folder", "emoji": "📂"},
    {"shortcode": "card_file_box", "emoji": "🗃️"},
    {"shortcode": "file_cabinet", "emoji": "🗄️"},
    {"shortcode": "wastebasket", "emoji": "🗑️"},
    {"shortcode": "inbox_tray", "emoji": "📥"},
    {"shortcode": "outbox_tray", "emoji": "📤"},
    {"shortcode": "package", "emoji": "📦"},
    {"shortcode": "envelope", "emoji": "✉️"},
    {"shortcode": "email", "emoji": "📧"},
    {"shortcode": "incoming_envelope", "emoji": "📨"},
    {"shortcode": "mailbox", "emoji": "📫"},
    {"shortcode": "mailbox_with_mail", "emoji": "📬"},

    # Documents & Writing
    {"shortcode": "memo", "emoji": "📝"},
    {"shortcode": "page_facing_up", "emoji": "📄"},
    {"shortcode": "page_with_curl", "emoji": "📃"},
    {"shortcode": "bookmark_tabs", "emoji": "📑"},
    {"shortcode": "bookmark", "emoji": "🔖"},
    {"shortcode": "label", "emoji": "🏷️"},
    {"shortcode": "newspaper", "emoji": "📰"},
    {"shortcode": "scroll", "emoji": "📜"},
    {"shortcode": "clipboard", "emoji": "📋"},
    {"shortcode": "pencil", "emoji": "✏️"},
    {"shortcode": "pen", "emoji": "🖊️"},
    {"shortcode": "fountain_pen", "emoji": "🖋️"},
    {"shortcode": "paintbrush", "emoji": "🖌️"},
    {"shortcode": "crayon", "emoji": "🖍️"},

    # Security & Privacy
    {"shortcode": "lock", "emoji": "🔒"},
    {"shortcode": "unlock", "emoji": "🔓"},
    {"shortcode": "lock_with_ink_pen", "emoji": "🔏"},
    {"shortcode": "closed_lock_with_key", "emoji": "🔐"},
    {"shortcode": "key", "emoji": "🔑"},
    {"shortcode": "old_key", "emoji": "🗝️"},
    {"shortcode": "shield", "emoji": "🛡️"},
    {"shortcode": "crossed_swords", "emoji": "⚔️"},
    {"shortcode": "dagger", "emoji": "🗡️"},
    {"shortcode": "eye", "emoji": "👁️"},
    {"shortcode": "eyes", "emoji": "👀"},

    # Tools & Building
    {"shortcode": "hammer", "emoji": "🔨"},
    {"shortcode": "axe", "emoji": "🪓"},
    {"shortcode": "pick", "emoji": "⛏️"},
    {"shortcode": "hammer_and_pick", "emoji": "⚒️"},
    {"shortcode": "hammer_and_wrench", "emoji": "🛠️"},
    {"shortcode": "wrench", "emoji": "🔧"},
    {"shortcode": "nut_and_bolt", "emoji": "🔩"},
    {"shortcode": "gear", "emoji": "⚙️"},
    {"shortcode": "chains", "emoji": "⛓️"},
    {"shortcode": "magnet", "emoji": "🧲"},
    {"shortcode": "scissors", "emoji": "✂️"},
    {"shortcode": "toolbox", "emoji": "🧰"},
    {"shortcode": "broom", "emoji": "🧹"},
    {"shortcode": "plunger", "emoji": "🪠"},

    # Time & Calendar
    {"shortcode": "watch", "emoji": "⌚"},
    {"shortcode": "alarm_clock", "emoji": "⏰"},
    {"shortcode": "stopwatch", "emoji": "⏱️"},
    {"shortcode": "timer_clock", "emoji": "⏲️"},
    {"shortcode": "clock", "emoji": "🕐"},
    {"shortcode": "hourglass", "emoji": "⌛"},
    {"shortcode": "hourglass_flowing_sand", "emoji": "⏳"},
    {"shortcode": "calendar", "emoji": "📅"},
    {"shortcode": "date", "emoji": "📆"},
    {"shortcode": "spiral_calendar", "emoji": "🗓️"},

    # Money & Business
    {"shortcode": "dollar", "emoji": "💵"},
    {"shortcode": "euro", "emoji": "💶"},
    {"shortcode": "pound", "emoji": "💷"},
    {"shortcode": "yen", "emoji": "💴"},
    {"shortcode": "money_with_wings", "emoji": "💸"},
    {"shortcode": "credit_card", "emoji": "💳"},
    {"shortcode": "chart", "emoji": "💹"},
    {"shortcode": "chart_with_upwards_trend", "emoji": "📈"},
    {"shortcode": "chart_with_downwards_trend", "emoji": "📉"},
    {"shortcode": "bar_chart", "emoji": "📊"},
    {"shortcode": "briefcase", "emoji": "💼"},

    # Network & Web
    {"shortcode": "globe_with_meridians", "emoji": "🌐"},
    {"shortcode": "earth_americas", "emoji": "🌎"},
    {"shortcode": "earth_europe", "emoji": "🌍"},
    {"shortcode": "earth_asia", "emoji": "🌏"},
    {"shortcode": "signal_strength", "emoji": "📶"},
    {"shortcode": "link", "emoji": "🔗"},
    {"shortcode": "chains", "emoji": "⛓️"},

    # Information
    {"shortcode": "information_source", "emoji": "ℹ️"},
    {"shortcode": "abc", "emoji": "🔤"},
    {"shortcode": "symbols", "emoji": "🔣"},
    {"shortcode": "1234", "emoji": "🔢"},
    {"shortcode": "hash", "emoji": "#️⃣"},
    {"shortcode": "asterisk", "emoji": "*️⃣"},
    {"shortcode": "zero", "emoji": "0️⃣"},
    {"shortcode": "one", "emoji": "1️⃣"},
    {"shortcode": "two", "emoji": "2️⃣"},
    {"shortcode": "three", "emoji": "3️⃣"},
    {"shortcode": "four", "emoji": "4️⃣"},
    {"shortcode": "five", "emoji": "5️⃣"},
    {"shortcode": "six", "emoji": "6️⃣"},
    {"shortcode": "seven", "emoji": "7️⃣"},
    {"shortcode": "eight", "emoji": "8️⃣"},
    {"shortcode": "nine", "emoji": "9️⃣"},
    {"shortcode": "keycap_ten", "emoji": "🔟"},

    # Signs & Labels
    {"shortcode": "free", "emoji": "🆓"},
    {"shortcode": "new", "emoji": "🆕"},
    {"shortcode": "up", "emoji": "🆙"},
    {"shortcode": "cool", "emoji": "🆒"},
    {"shortcode": "ok", "emoji": "🆗"},
    {"shortcode": "ng", "emoji": "🆖"},
    {"shortcode": "sos", "emoji": "🆘"},
    {"shortcode": "id", "emoji": "🆔"},
    {"shortcode": "vs", "emoji": "🆚"},
    {"shortcode": "atm", "emoji": "🏧"},
    {"shortcode": "cl", "emoji": "🆑"},
    {"shortcode": "ab", "emoji": "🆎"},
    {"shortcode": "a", "emoji": "🅰️"},
    {"shortcode": "b", "emoji": "🅱️"},
    {"shortcode": "o", "emoji": "🅾️"},
    {"shortcode": "parking", "emoji": "🅿️"},
    {"shortcode": "wc", "emoji": "🚾"},

    # Weather & Nature
    {"shortcode": "sunny", "emoji": "☀️"},
    {"shortcode": "cloud", "emoji": "☁️"},
    {"shortcode": "partly_sunny", "emoji": "⛅"},
    {"shortcode": "rain_cloud", "emoji": "🌧️"},
    {"shortcode": "snow_cloud", "emoji": "🌨️"},
    {"shortcode": "thunder_cloud_and_rain", "emoji": "⛈️"},
    {"shortcode": "tornado", "emoji": "🌪️"},
    {"shortcode": "fog", "emoji": "🌫️"},
    {"shortcode": "rainbow", "emoji": "🌈"},
    {"shortcode": "snowflake", "emoji": "❄️"},
    {"shortcode": "snowman", "emoji": "⛄"},
    {"shortcode": "comet", "emoji": "☄️"},
    {"shortcode": "volcano", "emoji": "🌋"},
    {"shortcode": "ocean", "emoji": "🌊"},
    {"shortcode": "droplet", "emoji": "💧"},
    {"shortcode": "sweat_drops", "emoji": "💦"},

    # Animals
    {"shortcode": "dog", "emoji": "🐕"},
    {"shortcode": "cat", "emoji": "🐈"},
    {"shortcode": "mouse", "emoji": "🐁"},
    {"shortcode": "rabbit", "emoji": "🐇"},
    {"shortcode": "fox", "emoji": "🦊"},
    {"shortcode": "bear", "emoji": "🐻"},
    {"shortcode": "panda", "emoji": "🐼"},
    {"shortcode": "koala", "emoji": "🐨"},
    {"shortcode": "tiger", "emoji": "🐯"},
    {"shortcode": "lion", "emoji": "🦁"},
    {"shortcode": "cow", "emoji": "🐄"},
    {"shortcode": "pig", "emoji": "🐷"},
    {"shortcode": "frog", "emoji": "🐸"},
    {"shortcode": "monkey", "emoji": "🐒"},
    {"shortcode": "chicken", "emoji": "🐔"},
    {"shortcode": "penguin", "emoji": "🐧"},
    {"shortcode": "bird", "emoji": "🐦"},
    {"shortcode": "eagle", "emoji": "🦅"},
    {"shortcode": "duck", "emoji": "🦆"},
    {"shortcode": "owl", "emoji": "🦉"},
    {"shortcode": "bat", "emoji": "🦇"},
    {"shortcode": "shark", "emoji": "🦈"},
    {"shortcode": "whale", "emoji": "🐋"},
    {"shortcode": "dolphin", "emoji": "🐬"},
    {"shortcode": "fish", "emoji": "🐟"},
    {"shortcode": "octopus", "emoji": "🐙"},
    {"shortcode": "butterfly", "emoji": "🦋"},
    {"shortcode": "bug", "emoji": "🐛"},
    {"shortcode": "ant", "emoji": "🐜"},
    {"shortcode": "bee", "emoji": "🐝"},
    {"shortcode": "beetle", "emoji": "🪲"},
    {"shortcode": "spider", "emoji": "🕷️"},
    {"shortcode": "scorpion", "emoji": "🦂"},
    {"shortcode": "snake", "emoji": "🐍"},
    {"shortcode": "turtle", "emoji": "🐢"},
    {"shortcode": "crocodile", "emoji": "🐊"},
    {"shortcode": "dragon", "emoji": "🐉"},
    {"shortcode": "unicorn", "emoji": "🦄"},

    # Food & Drink
    {"shortcode": "coffee", "emoji": "☕"},
    {"shortcode": "tea", "emoji": "🍵"},
    {"shortcode": "beer", "emoji": "🍺"},
    {"shortcode": "wine_glass", "emoji": "🍷"},
    {"shortcode": "cocktail", "emoji": "🍸"},
    {"shortcode": "pizza", "emoji": "🍕"},
    {"shortcode": "hamburger", "emoji": "🍔"},
    {"shortcode": "fries", "emoji": "🍟"},
    {"shortcode": "hotdog", "emoji": "🌭"},
    {"shortcode": "taco", "emoji": "🌮"},
    {"shortcode": "burrito", "emoji": "🌯"},
    {"shortcode": "popcorn", "emoji": "🍿"},
    {"shortcode": "doughnut", "emoji": "🍩"},
    {"shortcode": "cookie", "emoji": "🍪"},
    {"shortcode": "cake", "emoji": "🎂"},
    {"shortcode": "ice_cream", "emoji": "🍨"},
    {"shortcode": "apple", "emoji": "🍎"},
    {"shortcode": "banana", "emoji": "🍌"},
    {"shortcode": "grapes", "emoji": "🍇"},
    {"shortcode": "watermelon", "emoji": "🍉"},
    {"shortcode": "strawberry", "emoji": "🍓"},
    {"shortcode": "peach", "emoji": "🍑"},
    {"shortcode": "lemon", "emoji": "🍋"},
    {"shortcode": "avocado", "emoji": "🥑"},
    {"shortcode": "eggplant", "emoji": "🍆"},
    {"shortcode": "carrot", "emoji": "🥕"},
    {"shortcode": "corn", "emoji": "🌽"},
    {"shortcode": "hot_pepper", "emoji": "🌶️"},

    # Sports & Activities
    {"shortcode": "soccer", "emoji": "⚽"},
    {"shortcode": "basketball", "emoji": "🏀"},
    {"shortcode": "football", "emoji": "🏈"},
    {"shortcode": "baseball", "emoji": "⚾"},
    {"shortcode": "tennis", "emoji": "🎾"},
    {"shortcode": "volleyball", "emoji": "🏐"},
    {"shortcode": "rugby_football", "emoji": "🏉"},
    {"shortcode": "8ball", "emoji": "🎱"},
    {"shortcode": "golf", "emoji": "⛳"},
    {"shortcode": "dart", "emoji": "🎯"},
    {"shortcode": "bowling", "emoji": "🎳"},
    {"shortcode": "video_game", "emoji": "🎮"},
    {"shortcode": "joystick", "emoji": "🕹️"},
    {"shortcode": "slot_machine", "emoji": "🎰"},
    {"shortcode": "game_die", "emoji": "🎲"},
    {"shortcode": "jigsaw", "emoji": "🧩"},

    # Music & Entertainment
    {"shortcode": "musical_note", "emoji": "🎵"},
    {"shortcode": "notes", "emoji": "🎶"},
    {"shortcode": "microphone", "emoji": "🎤"},
    {"shortcode": "headphones", "emoji": "🎧"},
    {"shortcode": "guitar", "emoji": "🎸"},
    {"shortcode": "trumpet", "emoji": "🎺"},
    {"shortcode": "violin", "emoji": "🎻"},
    {"shortcode": "drum", "emoji": "🥁"},
    {"shortcode": "clapper", "emoji": "🎬"},
    {"shortcode": "ticket", "emoji": "🎫"},
    {"shortcode": "tickets", "emoji": "🎟️"},
    {"shortcode": "performing_arts", "emoji": "🎭"},
    {"shortcode": "art", "emoji": "🎨"},
    {"shortcode": "circus_tent", "emoji": "🎪"},

    # Travel & Places
    {"shortcode": "car", "emoji": "🚗"},
    {"shortcode": "taxi", "emoji": "🚕"},
    {"shortcode": "bus", "emoji": "🚌"},
    {"shortcode": "ambulance", "emoji": "🚑"},
    {"shortcode": "fire_engine", "emoji": "🚒"},
    {"shortcode": "police_car", "emoji": "🚓"},
    {"shortcode": "truck", "emoji": "🚚"},
    {"shortcode": "train", "emoji": "🚆"},
    {"shortcode": "ship", "emoji": "🚢"},
    {"shortcode": "helicopter", "emoji": "🚁"},
    {"shortcode": "anchor", "emoji": "⚓"},
    {"shortcode": "fuel_pump", "emoji": "⛽"},
    {"shortcode": "vertical_traffic_light", "emoji": "🚦"},
    {"shortcode": "house", "emoji": "🏠"},
    {"shortcode": "office", "emoji": "🏢"},
    {"shortcode": "hospital", "emoji": "🏥"},
    {"shortcode": "bank", "emoji": "🏦"},
    {"shortcode": "hotel", "emoji": "🏨"},
    {"shortcode": "school", "emoji": "🏫"},
    {"shortcode": "factory", "emoji": "🏭"},
    {"shortcode": "stadium", "emoji": "🏟️"},

    # Flags & Symbols
    {"shortcode": "checkered_flag", "emoji": "🏁"},
    {"shortcode": "triangular_flag_on_post", "emoji": "🚩"},
    {"shortcode": "crossed_flags", "emoji": "🎌"},
    {"shortcode": "black_flag", "emoji": "🏴"},
    {"shortcode": "white_flag", "emoji": "🏳️"},
    {"shortcode": "rainbow_flag", "emoji": "🏳️‍🌈"},
    {"shortcode": "pirate_flag", "emoji": "🏴‍☠️"},

    # Miscellaneous
    {"shortcode": "bell", "emoji": "🔔"},
    {"shortcode": "no_bell", "emoji": "🔕"},
    {"shortcode": "speaker", "emoji": "🔈"},
    {"shortcode": "mute", "emoji": "🔇"},
    {"shortcode": "loud_sound", "emoji": "🔊"},
    {"shortcode": "mega", "emoji": "📣"},
    {"shortcode": "loudspeaker", "emoji": "📢"},
    {"shortcode": "speech_balloon", "emoji": "💬"},
    {"shortcode": "thought_balloon", "emoji": "💭"},
    {"shortcode": "zzz", "emoji": "💤"},
    {"shortcode": "mag", "emoji": "🔍"},
    {"shortcode": "mag_right", "emoji": "🔎"},
    {"shortcode": "microscope", "emoji": "🔬"},
    {"shortcode": "telescope", "emoji": "🔭"},
    {"shortcode": "pill", "emoji": "💊"},
    {"shortcode": "syringe", "emoji": "💉"},
    {"shortcode": "stethoscope", "emoji": "🩺"},
    {"shortcode": "dna", "emoji": "🧬"},
    {"shortcode": "microbe", "emoji": "🦠"},
    {"shortcode": "petri_dish", "emoji": "🧫"},
    {"shortcode": "test_tube", "emoji": "🧪"},
    {"shortcode": "thermometer", "emoji": "🌡️"},
    {"shortcode": "candle", "emoji": "🕯️"},
    {"shortcode": "gift", "emoji": "🎁"},
    {"shortcode": "ribbon", "emoji": "🎀"},
    {"shortcode": "balloon", "emoji": "🎈"},
    {"shortcode": "crystal_ball", "emoji": "🔮"},
    {"shortcode": "nazar_amulet", "emoji": "🧿"},
    {"shortcode": "joker", "emoji": "🃏"},
    {"shortcode": "mahjong", "emoji": "🀄"},
    {"shortcode": "spades", "emoji": "♠️"},
    {"shortcode": "hearts", "emoji": "♥️"},
    {"shortcode": "diamonds", "emoji": "♦️"},
    {"shortcode": "clubs", "emoji": "♣️"},
    {"shortcode": "chess_pawn", "emoji": "♟️"},
    {"shortcode": "hand", "emoji": "✋"},
    {"shortcode": "point_up", "emoji": "☝️"},
    {"shortcode": "point_down", "emoji": "👇"},
    {"shortcode": "point_left", "emoji": "👈"},
    {"shortcode": "point_right", "emoji": "👉"},
    {"shortcode": "wave", "emoji": "👋"},
    {"shortcode": "pinched_fingers", "emoji": "🤌"},
    {"shortcode": "victory_hand", "emoji": "✌️"},
    {"shortcode": "crossed_fingers", "emoji": "🤞"},
    {"shortcode": "call_me_hand", "emoji": "🤙"},
    {"shortcode": "fist", "emoji": "✊"},
    {"shortcode": "punch", "emoji": "👊"},
    {"shortcode": "writing_hand", "emoji": "✍️"},
]


class NtfyService:
    """Service to interact with the NTFY server."""

    def __init__(self, base_url: Optional[str] = None, public_url: Optional[str] = None):
        """
        Initialize the NTFY service.

        Args:
            base_url: NTFY server URL for internal communication. Defaults to local container or env var.
            public_url: NTFY public URL for documentation/examples. Defaults to env var or constructs from DOMAIN.
        """
        # Internal URL for container-to-container communication
        self.base_url = base_url or os.environ.get("NTFY_BASE_URL", "http://n8n_ntfy:80")
        self.base_url = self.base_url.rstrip("/")

        # Public URL for external access (used in examples/documentation)
        if public_url:
            self.public_url = public_url.rstrip("/")
        else:
            # Try NTFY_PUBLIC_URL first, then construct from DOMAIN
            env_public_url = os.environ.get("NTFY_PUBLIC_URL")
            if env_public_url:
                self.public_url = env_public_url.rstrip("/")
            else:
                # Construct from DOMAIN env var (e.g., ntfy.loft.aero)
                domain = os.environ.get("DOMAIN", "")
                if domain:
                    self.public_url = f"https://ntfy.{domain}"
                else:
                    # Fallback to placeholder
                    self.public_url = "https://ntfy.your-domain.com"

    def is_own_server(self, server_url: Optional[str]) -> bool:
        """True if server_url points at the ntfy server this console manages.

        Used to decide whether a notification channel may be sent NTFY_TOKEN;
        the token must never be sent to a third-party server such as ntfy.sh.
        """
        if not server_url:
            return False
        try:
            target = urlsplit(server_url.strip())
        except ValueError:
            return False
        host = (target.hostname or "").lower()
        if not host:
            return False
        if host in LOCAL_NTFY_HOSTS:
            return True
        target_path = target.path.rstrip("/")
        candidates = [self.base_url, self.public_url]
        domain = os.environ.get("DOMAIN", "").strip()
        if domain:
            # nginx also proxies the server at https://<domain>/ntfy/
            candidates.append(f"https://{domain}/ntfy")
        for candidate in candidates:
            if not candidate:
                continue
            try:
                own = urlsplit(candidate)
            except ValueError:
                continue
            if (own.hostname or "").lower() != host or own.port != target.port:
                continue
            own_path = own.path.rstrip("/")
            if target_path == own_path or target_path.startswith(own_path + "/"):
                return True
        return False

    def auth_headers(self, auth_token: Optional[str] = None) -> Dict[str, str]:
        """Authorization header for requests to this console's ntfy server."""
        token = auth_token or get_ntfy_token()
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def health_check(self) -> Dict[str, Any]:
        """
        Check NTFY server health.

        Returns:
            Health status dict with 'healthy' boolean and details.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/v1/health")

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "healthy": data.get("healthy", False),
                        "status": "connected",
                        "message": "NTFY server is healthy",
                        "details": data
                    }
                else:
                    return {
                        "healthy": False,
                        "status": "error",
                        "message": f"NTFY returned status {response.status_code}",
                        "details": None
                    }
        except httpx.ConnectError:
            return {
                "healthy": False,
                "status": "disconnected",
                "message": "Cannot connect to NTFY server",
                "details": None
            }
        except Exception as e:
            logger.error(f"NTFY health check error: {e}")
            return {
                "healthy": False,
                "status": "error",
                "message": str(e),
                "details": None
            }

    async def send_message(
        self,
        topic: str,
        message: str,
        title: Optional[str] = None,
        priority: int = 3,
        tags: Optional[List[str]] = None,
        click: Optional[str] = None,
        attach: Optional[str] = None,
        icon: Optional[str] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
        delay: Optional[str] = None,
        email: Optional[str] = None,
        markdown: bool = False,
        auth_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a message to an NTFY topic.

        Args:
            topic: Target topic name
            message: Message body
            title: Optional message title
            priority: Priority level 1-5
            tags: List of tags/emojis
            click: URL to open on notification click
            attach: Attachment URL
            icon: Custom icon URL
            actions: List of action button definitions
            delay: Delay/schedule string (e.g., "30m", "tomorrow 10am")
            email: Forward notification to this email
            markdown: Enable markdown formatting
            auth_token: Optional authentication token

        Returns:
            Result dict with success status and details.
        """
        try:
            headers = {
                "Content-Type": "application/json",
                **self.auth_headers(auth_token),
            }

            # Build JSON payload
            payload = {
                "topic": topic,
                "message": message,
            }

            if title:
                payload["title"] = title

            if priority != 3:
                payload["priority"] = priority

            if tags:
                payload["tags"] = tags

            if click:
                payload["click"] = click

            if attach:
                payload["attach"] = attach

            if icon:
                payload["icon"] = icon

            if actions:
                payload["actions"] = actions

            if delay:
                payload["delay"] = delay

            if email:
                payload["email"] = email

            if markdown:
                payload["markdown"] = True

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )

                if response.status_code in (200, 201):
                    result = response.json()
                    return {
                        "success": True,
                        "message_id": result.get("id"),
                        "topic": topic,
                        "scheduled": delay is not None,
                        "response": result
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "error": "Authentication required or invalid token (check NTFY_TOKEN in .env)",
                        "status_code": 401
                    }
                elif response.status_code == 403:
                    return {
                        "success": False,
                        "error": "Access denied to this topic",
                        "status_code": 403
                    }
                elif response.status_code == 429:
                    return {
                        "success": False,
                        "error": "Rate limit exceeded",
                        "status_code": 429
                    }
                else:
                    error_text = response.text
                    try:
                        error_json = response.json()
                        error_text = error_json.get("error", error_text)
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "error": f"NTFY error ({response.status_code}): {error_text}",
                        "status_code": response.status_code
                    }

        except httpx.ConnectError:
            return {
                "success": False,
                "error": "Cannot connect to NTFY server"
            }
        except Exception as e:
            logger.error(f"Error sending NTFY message: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def send_with_template(
        self,
        topic: str,
        template_name: str,
        data: Dict[str, Any],
        priority: Optional[int] = None,
        extra_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send a message using NTFY's built-in template support.

        Args:
            topic: Target topic
            template_name: Template name ('github', 'grafana', 'alertmanager', or custom)
            data: JSON data to be processed by the template
            priority: Override template priority
            extra_tags: Additional tags to append

        Returns:
            Result dict.
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Template": template_name,
                **self.auth_headers(),
            }

            if priority:
                headers["X-Priority"] = str(priority)

            if extra_tags:
                headers["X-Tags"] = ",".join(extra_tags)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/{topic}",
                    headers=headers,
                    json=data
                )

                if response.status_code in (200, 201):
                    return {
                        "success": True,
                        "response": response.json() if response.text else None
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Template error ({response.status_code}): {response.text}"
                    }

        except Exception as e:
            logger.error(f"Error sending templated message: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def build_action(
        self,
        action_type: str,
        label: str,
        url: Optional[str] = None,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        intent: Optional[str] = None,
        extras: Optional[Dict[str, str]] = None,
        clear: bool = False,
    ) -> Dict[str, Any]:
        """
        Build an action button definition.

        Args:
            action_type: 'view', 'http', or 'broadcast'
            label: Button label text
            url: URL for view/http actions
            method: HTTP method for http actions
            headers: Headers for http actions
            body: Body for http actions
            intent: Android intent for broadcast actions
            extras: Android extras for broadcast actions
            clear: Clear notification after action

        Returns:
            Action definition dict.
        """
        action = {
            "action": action_type,
            "label": label,
        }

        if action_type == "view":
            if url:
                action["url"] = url
            if clear:
                action["clear"] = True

        elif action_type == "http":
            if url:
                action["url"] = url
            if method != "POST":
                action["method"] = method
            if headers:
                action["headers"] = headers
            if body:
                action["body"] = body
            if clear:
                action["clear"] = True

        elif action_type == "broadcast":
            if intent:
                action["intent"] = intent
            if extras:
                action["extras"] = extras
            if clear:
                action["clear"] = True

        return action

    def get_priority_name(self, level: int) -> str:
        """Get priority name from numeric level."""
        return PRIORITY_NAMES.get(level, "default")

    def get_priority_value(self, name: str) -> int:
        """Get priority numeric value from name."""
        return PRIORITY_VALUES.get(name.lower(), 3)

    def get_emoji_suggestions(self, category: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get emoji suggestions by category.

        Args:
            category: Specific category or None for all

        Returns:
            Dict of category -> emoji shortcode list.
        """
        if category:
            return {category: COMMON_EMOJIS.get(category, [])}
        return COMMON_EMOJIS

    def validate_delay(self, delay: str) -> Dict[str, Any]:
        """
        Validate a delay string.

        Args:
            delay: Delay string like "30m", "2h", "tomorrow 10am"

        Returns:
            Validation result with parsed info.
        """
        # Duration pattern: number + unit
        duration_pattern = r'^(\d+)\s*(s|sec|second|seconds|m|min|minute|minutes|h|hour|hours|d|day|days)$'

        # Check duration format
        match = re.match(duration_pattern, delay.strip(), re.IGNORECASE)
        if match:
            value = int(match.group(1))
            unit = match.group(2).lower()

            # Convert to seconds for validation
            multipliers = {
                's': 1, 'sec': 1, 'second': 1, 'seconds': 1,
                'm': 60, 'min': 60, 'minute': 60, 'minutes': 60,
                'h': 3600, 'hour': 3600, 'hours': 3600,
                'd': 86400, 'day': 86400, 'days': 86400,
            }
            seconds = value * multipliers.get(unit, 1)

            # NTFY limits: min 10s, max 3 days
            if seconds < 10:
                return {"valid": False, "error": "Minimum delay is 10 seconds"}
            if seconds > 259200:  # 3 days
                return {"valid": False, "error": "Maximum delay is 3 days"}

            return {
                "valid": True,
                "type": "duration",
                "value": delay,
                "seconds": seconds
            }

        # Timestamp pattern: Unix timestamp
        if delay.isdigit():
            ts = int(delay)
            now = int(datetime.now(UTC).timestamp())
            if ts <= now:
                return {"valid": False, "error": "Timestamp must be in the future"}
            if ts > now + 259200:
                return {"valid": False, "error": "Maximum delay is 3 days"}
            return {
                "valid": True,
                "type": "timestamp",
                "value": delay,
                "seconds": ts - now
            }

        # Natural language - let NTFY handle validation
        natural_patterns = [
            r'tomorrow',
            r'today',
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'\d{1,2}:\d{2}\s*(am|pm)?',
            r'\d{1,2}\s*(am|pm)',
        ]

        for pattern in natural_patterns:
            if re.search(pattern, delay, re.IGNORECASE):
                return {
                    "valid": True,
                    "type": "natural",
                    "value": delay,
                    "note": "NTFY will parse this naturally"
                }

        return {
            "valid": False,
            "error": f"Invalid delay format: {delay}"
        }

    def format_message_preview(
        self,
        title: Optional[str],
        message: str,
        priority: int,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Format a message for preview display.

        Returns dict with formatted preview components.
        """
        # Build a set of known emoji shortcodes from COMMON_EMOJIS (flat list)
        known_shortcodes = {e.get("shortcode", "") for e in COMMON_EMOJIS}

        # Convert tags to emojis where possible
        emoji_tags = []
        text_tags = []

        if tags:
            for tag in tags:
                if tag in known_shortcodes:
                    emoji_tags.append(tag)
                else:
                    text_tags.append(tag)

        return {
            "title": title,
            "message": message,
            "priority": self.get_priority_name(priority),
            "priority_level": priority,
            "emoji_tags": emoji_tags,
            "text_tags": text_tags,
        }


# Create singleton instance
ntfy_service = NtfyService()
