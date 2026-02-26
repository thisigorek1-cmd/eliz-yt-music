import os
from aiogram import F, Dispatcher, Bot
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    FSInputFile,
    ReplyKeyboardRemove,
)
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import API_ID, API_HASH, USER_SESSION
from database import get_sql, ensure_user, increase_user_download
from database import log_download
from datetime import datetime

# ===== USERBOT =====
tg_user = TelegramClient(
    StringSession(USER_SESSION),
    API_ID,
    API_HASH
)

# ===== PATHS =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEARCH_VIDEO = os.path.join(BASE_DIR, "assets", "search.mp4")

# ===== CACHE =====
search_cache = {}
track_cache = {}
SEARCH_VIDEO_ID = None

async def increase_daily_count(user_id):
    conn = get_sql()
    cursor = conn.cursor()

    today = str(datetime.now().date())

    cursor.execute(
        "SELECT daily_count, last_reset FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return

    daily_count, last_reset = row

    if last_reset != today:
        daily_count = 0

    cursor.execute(
        "UPDATE users SET daily_count=?, last_reset=? WHERE user_id=?",
        (daily_count + 1, today, user_id)
    )

    conn.commit()
    conn.close()

# ===== CACHE WARMUP =====
async def warmup_cache():

    conn = get_sql()
    cursor = conn.cursor()

    cursor.execute("SELECT query, file_id FROM tracks")
    rows = cursor.fetchall()

    for query, file_id in rows:
        if file_id:
            track_cache[query] = file_id

    conn.close()

    print(f"Cache warmed: {len(track_cache)} tracks loaded")

# ===== KEYBOARD =====
def build_keyboard(user_id):
    data = search_cache[user_id]
    results = data["results"]

    buttons = []

    for i, entry in enumerate(results[:7]):

        title = entry.title or ""
        artist = entry.description or ""

        # Если в title уже есть разделитель — значит артист уже внутри
        if " - " in title:
            button_text = title
        else:
            if artist:
                button_text = f"{artist} - {title}"
            else:
                button_text = title

        buttons.append([
            InlineKeyboardButton(
                text=button_text[:50],
                callback_data=f"track_{i}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ===== HANDLERS REGISTRATION =====
def register_music_handlers(dp: Dispatcher, bot: Bot):

    @dp.message(
    F.chat.type == "private",
    F.text,
    ~F.text.regexp(r"^\d+$"),   # ← ВОТ ЭТУ СТРОКУ ДОБАВЬ
    ~F.text.in_(["Профиль 👤", "Донат 🍩"]),
    ~F.text.startswith("/")
)
    async def search_handler(message: Message):

        text = message.text.strip()

        if text.startswith("/"):
            return

        try:
            inline_results = await tg_user.inline_query("lybot", text)

            if not inline_results:
                await message.answer("Ничего не найдено")
                return

            results = inline_results[:7]

            search_cache[message.from_user.id] = {
                "results": results
            }

            keyboard = build_keyboard(message.from_user.id)

            global SEARCH_VIDEO_ID

            if SEARCH_VIDEO_ID:
                msg = await message.answer_video(
                    video=SEARCH_VIDEO_ID,
                    caption="🎧 <b>Ищем треки...</b>",
                    parse_mode="HTML"
                )
            else:
                video = FSInputFile(SEARCH_VIDEO)
                sent = await message.answer_video(
                    video=video,
                    caption="🎧 <b>Ищем треки...</b>",
                    parse_mode="HTML"
                )
                SEARCH_VIDEO_ID = sent.video.file_id
                msg = sent

            await msg.edit_caption(
                caption="🎵 <b>Выбери трек:</b>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        except Exception as e:
            print("SEARCH ERROR:", e)
            await message.answer("Ошибка поиска")

    @dp.callback_query(F.data.startswith("track_"))
    async def download_track(callback: CallbackQuery):

        # Отвечаем мгновенно
        try:
            await callback.answer()
        except:
            pass

        user_id = callback.from_user.id

        # ===== ПРОВЕРКА ЛИМИТА =====
        conn = get_sql()
        cursor = conn.cursor()

        today = str(datetime.now().date())

        cursor.execute(
            "SELECT daily_count, last_reset, premium_until FROM users WHERE user_id=?",
            (user_id,)
        )
        row = cursor.fetchone()

        if not row:
            ensure_user(user_id)
            daily_count = 0
            last_reset = today
            premium_until = None
        else:
            daily_count, last_reset, premium_until = row

        # сброс если новый день
        if last_reset != today:
            daily_count = 0
            cursor.execute(
                "UPDATE users SET daily_count=0, last_reset=? WHERE user_id=?",
                (today, user_id)
            )
            conn.commit()

        # проверяем премиум
        is_premium = False

        if premium_until:
            if datetime.fromisoformat(premium_until) > datetime.now():
                is_premium = True

        FREE_LIMIT = 3

        # 🚫 лимит только для бесплатных
        if not is_premium and daily_count >= FREE_LIMIT:
            conn.close()
            await callback.message.answer(
                "🚫 <b>Лимит бесплатных треков — 3 в день</b>\n\n"
                "⭐ Premium снимает все ограничения.",
                parse_mode="HTML"
            )
            return

        conn.close()

        if user_id not in search_cache:
            await callback.message.answer("Поиск устарел")
            return

        index = int(callback.data.split("_")[1])
        results = search_cache[user_id]["results"]

        if index >= len(results):
            await callback.message.answer("Трек недоступен")
            return

        selected_result = results[index]

        raw_title = selected_result.title or ""
        raw_artist = selected_result.description or ""

        # Если в названии уже есть " - "
        if " - " in raw_title:
            artist, track_name = raw_title.split(" - ", 1)
        else:
            artist = raw_artist
            track_name = raw_title

        query = f"{artist} - {track_name}" if artist else track_name
        title = track_name
        performer = artist

        # ===== RAM CACHE =====
        if query in track_cache:
            file_id = track_cache[query]

            await callback.message.answer_audio(
                audio=file_id,
                title=title,
                performer=performer,
                caption='🎵 <a href="https://t.me/ElizCityBot">Все треки можно найти тут 🔗</a>',
                parse_mode="HTML"
            )

            ensure_user(user_id)
            increase_user_download(user_id)

            return

        # ===== DB CACHE =====
        conn = get_sql()
        cursor = conn.cursor()

        cursor.execute("SELECT file_id FROM tracks WHERE query = ?", (query,))
        row = cursor.fetchone()

        conn.close()

        if row:
            file_id = row[0]
            track_cache[query] = file_id

            await callback.message.answer_audio(
                audio=file_id,
                title=title,
                performer=performer,
                caption='🎵 <a href="https://t.me/ElizCityBot">Все треки можно найти тут 🔗</a>',
                parse_mode="HTML"
            )

            ensure_user(user_id)
            increase_user_download(user_id)

            return

        # ===== TELEGRAM CLICK =====
        try:
            tg_msg = await selected_result.click(entity="me")

            if not tg_msg or not tg_msg.document:
                await callback.message.answer("Не удалось получить файл")
                return

            file_bytes = await tg_user.download_media(tg_msg, bytes)
            await tg_msg.delete()

            if not file_bytes:
                await callback.message.answer("Ошибка загрузки файла")
                return

            from aiogram.types import BufferedInputFile

            audio_file = BufferedInputFile(file_bytes, filename="track.mp3")

            bot_msg = await callback.message.answer_audio(
                audio=audio_file,
                title=title,
                performer=performer,
                caption='🎵 <a href="https://t.me/ElizCityBot">Все треки можно найти тут 🔗</a>',
                parse_mode="HTML"
            )

            ensure_user(user_id)
            increase_user_download(user_id)

            file_id = bot_msg.audio.file_id

            conn = get_sql()
            cursor = conn.cursor()

            cursor.execute(
                "INSERT OR IGNORE INTO tracks (query, title, file_id) VALUES (?, ?, ?)",
                (query, title, file_id)
            )

            conn.commit()
            conn.close()

            track_cache[query] = file_id

        except Exception as e:
            print("TG ERROR:", e)
            await callback.message.answer("Ошибка поиска трека")