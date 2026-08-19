"""All user-facing strings, Uzbek first then English, kept in one place so
localization/expansion later is a one-file change."""

WELCOME = (
    "🎬 Xush kelibsiz! / Welcome!\n\n"
    "Filmlar botiga xush kelibsiz. Film raqamini yuboring va men sizga filmni topib beraman.\n"
    "Welcome to the movie bot. Send a movie number and I'll find it for you.\n\n"
    "Boshlash uchun avval kanalimizga a'zo bo'ling. / To get started, please join our channel first."
)

HELP = (
    "ℹ️ Yordam / Help\n\n"
    "/movie <raqam> — Film raqami bo'yicha qidirish / Look up a movie by number\n"
    "/search <matn> — Nomi bo'yicha qidirish / Search by title\n"
    "/help — Ushbu xabar / This message\n\n"
    "Misol / Example: /movie 1025"
)

# Update NOT_SUBSCRIBED message
NOT_SUBSCRIBED = (
    "⚠️ Kino olish uchun quyidagi kanallarga a'zo bo'lishingiz kerak!\n\n"
    "1. Barcha kanallarga a'zo bo'ling\n"
    "2. So'ng 'A'zo bo'ldim' tugmasini bosing\n\n"
    "A'zo bo'lgandan so'ng kino olishingiz mumkin."
)

STILL_NOT_SUBSCRIBED = (
    "❌ Siz hali barcha kanallarga a'zo bo'lmagansiz!\n\n"
    "Iltimos, barcha kanallarga a'zo bo'ling va qaytadan urinib ko'ring."
)

SUBSCRIPTION_VERIFIED = (
    "✅ Rahmat! Siz tasdiqlandingiz. Endi film raqamini yuborishingiz mumkin.\n"
    "Thanks! You're verified. You can now send a movie number."
)

SEND_MOVIE_NUMBER = (
    "🎥 Film raqamini yuboring (masalan: 1025) yoki /search <nom> dan foydalaning.\n"
    "Send a movie number (e.g. 1025), or use /search <title>."
)

MOVIE_NOT_FOUND = (
    "❌ Bunday raqamli film topilmadi. Raqamni tekshirib qayta urinib ko'ring.\n"
    "No movie found with that number. Please double-check and try again."
)

INVALID_MOVIE_NUMBER = (
    "⚠️ Iltimos, to'g'ri film raqamini kiriting (faqat raqam).\n"
    "Please enter a valid movie number (digits only)."
)

RATE_LIMITED = (
    "⏳ Juda ko'p so'rov yubordingiz. Birozdan so'ng qayta urinib ko'ring.\n"
    "You're sending requests too fast. Please slow down and try again shortly."
)

GENERIC_ERROR = (
    "⚠️ Xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.\n"
    "Something went wrong. Please try again in a moment."
)

BANNED = (
    "🚫 Siz botdan foydalanishdan cheklangansiz.\n"
    "You have been restricted from using this bot."
)

NOT_ADMIN = (
    "🚫 Bu buyruq faqat administratorlar uchun.\n"
    "This command is for administrators only."
)

SUPER_ADMIN_ONLY = (
    "🚫 Bu buyruq faqat bosh administrator uchun.\n"
    "This command is for super admins only."
)

SEARCH_USAGE = "Foydalanish / Usage: /search <film nomi / movie title>"

SEARCH_NO_RESULTS = (
    "❌ Hech narsa topilmadi. Boshqa so'z bilan urinib ko'ring.\n"
    "No results found. Try a different search term."
)

BTN_JOIN_CHANNEL = "📢 Kanalga qo'shilish / Join Channel"
BTN_VERIFY = "✅ Tekshirish / Verify"
