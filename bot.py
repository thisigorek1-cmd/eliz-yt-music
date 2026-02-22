import asyncio # Добавлено для запуска бота
import os # Работа с файлами и путями
import sqlite3 # Работа с базой данных
import platform # Определение операционной системы для настройки ffmpeg

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    FSInputFile
) # Импорт типов из aiogram

from aiogram.filters import CommandStart # Фильтр для команды /start
from yt_dlp import YoutubeDL # Библиотека для скачивания аудио с YouTube
from config import BOT_TOKEN # Импорт токена и других настроек из config.py
from donate_menu import donate_keyboard # Импорт клавиатуры для доната из donate_menu.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton # Импорт типов для создания клавиатуры
from datetime import datetime, timedelta # Работа с датой и временем

from aiogram.client.session.aiohttp import AiohttpSession # Используем AiohttpSession для асинхронных запросов

session = AiohttpSession() 
bot = Bot(token=BOT_TOKEN, session=session) # Bot(token=BOT_TOKEN) 
dp = Dispatcher() # Dispatcher(bot)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DOWNLOAD_PATH = os.path.join(BASE_DIR, "downloads") # Папка для загрузки треков
PROFILE_PHOTO = os.path.join(BASE_DIR, "assets", "profile.jpg") # Фото для профиля (можно заменить на любое другое)
SEARCH_VIDEO = os.path.join(BASE_DIR, "assets", "search.mp4") # Видео для анимации поиска (можно заменить на любое короткое видео)
ADMIN_IDS = {8454715718}  # Множество ID администраторов (можно добавить несколько)

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

def main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Профиль 👤")],
            [KeyboardButton(text="Донат 🍩")]
        ],
        resize_keyboard=True
    )
    return keyboard

# ===== БАЗА ДАННЫХ =====
conn = sqlite3.connect("tracks.db") # Подключение к базе данных (создаст файл, если его нет)
cursor = conn.cursor() # Создаем курсор для выполнения SQL-запросов

cursor.execute("""
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_url TEXT UNIQUE,
    title TEXT,
    file_id TEXT,
    download_count INTEGER DEFAULT 0
)
""") # Создаем таблицу для треков, если ее нет. Добавляем поле download_count для статистики скачиваний каждого трека

# ===== ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ =====
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    daily_count INTEGER DEFAULT 0,
    last_reset TEXT,
    premium_until TEXT,
    total_downloads INTEGER DEFAULT 0
)
""")

conn.commit() # Сохраняем изменения в базе данных

try:
    cursor.execute("ALTER TABLE tracks ADD COLUMN download_count INTEGER DEFAULT 0")
    conn.commit()
except:
    pass

# --- ДОБАВЛЯЕМ КОЛОНКУ ЕСЛИ ЕЕ НЕТ ---
try:
    cursor.execute("ALTER TABLE users ADD COLUMN total_downloads INTEGER DEFAULT 0")
    conn.commit()
except:
    pass

# Хранилище найденных треков (временно в памяти)
search_cache = {}
# Кэш отправленных треков (url → file_id)
track_cache = {}
# Временная переменная для хранения ID видео при поиске
SEARCH_VIDEO_ID = None

# ===== СТАРТ =====
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "🎵 <b>Привет, я Eliz Music!</b>\n\n"
        "Найду тебе любой трек с YouTube.\n"
        "Просто напиши название трека — и я отправлю его тебе 🚀",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@dp.message(F.text == "Профиль 👤")
async def profile_handler(message: Message):

    user_id = message.from_user.id
    name = message.from_user.first_name
    today = datetime.now().date()

    cursor.execute(
        "SELECT daily_count, last_reset, premium_until, total_downloads FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()

    if not row:
        daily_count = 0
        last_reset = str(today)
        premium_until = None
        total_downloads = 0

        cursor.execute(
            "INSERT INTO users (user_id, daily_count, last_reset, total_downloads) VALUES (?, 0, ?, 0)",
            (user_id, str(today))
        )
        conn.commit()
    else:
        daily_count, last_reset, premium_until, total_downloads = row

    # Сброс если новый день
    if last_reset != str(today):
        cursor.execute(
            "UPDATE users SET daily_count = 0, last_reset = ? WHERE user_id = ?",
            (str(today), user_id)
        )
        conn.commit()
        daily_count = 0

    # Проверка премиума
    if premium_until and datetime.fromisoformat(premium_until) > datetime.now():
        status = "Премиум 👑"
        limit = 10
    else:
        status = "Бесплатный"
        limit = 3

    photo = FSInputFile(PROFILE_PHOTO)

    await message.answer_photo(
        photo=photo,
        caption=(
            f"👥 <b>Ваш профиль</b>\n\n"
            f"🥷🏻 Имя: {name}\n"
            f"🆔 ID: {user_id}\n\n"
            f"📌 Статус: {status}\n"
            f"🎵 Лимит треков сегодня: {daily_count}/{limit}\n\n"
            f"🔥 Всего треков найдено вами: {total_downloads}"
        ),
        parse_mode="HTML"
    )

@dp.message(F.text == "Донат 🍩")
async def donate_menu_handler(message: Message):

    await message.answer(
        "⭐️ Премиум доступ\n\n"
        "Бесплатно: 3 трека в день\n"
        "Премиум: 10 треков в день\n"
        "Срок действия: 30 дней",
        reply_markup=donate_keyboard()
    )

from aiogram.types import LabeledPrice

@dp.callback_query(F.data == "buy_premium")
async def buy_premium(callback: CallbackQuery):

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Премиум доступ",
        description="10 треков в день на 30 дней",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Премиум", amount=25)],
        payload="premium_30",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False
    )

    await callback.answer()

from aiogram.types import PreCheckoutQuery

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    user_id = message.from_user.id
    premium_until = datetime.now() + timedelta(days=30)

    cursor.execute(
        """
        INSERT INTO users (user_id, premium_until, daily_count, last_reset)
        VALUES (?, ?, 0, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET premium_until = excluded.premium_until
        """,
        (user_id, premium_until.isoformat(), str(datetime.now().date()))
    )
    conn.commit()

    await message.answer("Премиум активирован на 30 дней 🎉")

# ===== ПОИСК ТОП 5 =====
@dp.message(F.chat.type == "private", F.text)
async def search_handler(message: Message):

    text = message.text.strip()

    if text.startswith("/") or text in ["Профиль 👤", "Донат 🍩"]:
        return

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch15:{text}", download=False)

        results = info.get("entries", [])

        if not results:
            await message.answer("Ничего не найдено")
            return

        search_cache[message.from_user.id] = {
            "results": results,
            "page": 0
        }

        keyboard = build_keyboard(message.from_user.id)

        global SEARCH_VIDEO_ID

        if SEARCH_VIDEO_ID:
            loading_msg = await message.answer_video(
                video=SEARCH_VIDEO_ID,
                caption="🎧 <b>Ищем треки...</b>",
                parse_mode="HTML"
            )
        else:
            video = FSInputFile(SEARCH_VIDEO)
            msg = await message.answer_video(
                video=video,
                caption="🎧 <b>Ищем треки...</b>",
                parse_mode="HTML"
            )
            SEARCH_VIDEO_ID = msg.video.file_id
            loading_msg = msg

        await loading_msg.edit_caption(
            caption="🎵 <b>Выбери трек:</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except Exception as e:
        await message.answer("Ошибка поиска")
        print("SEARCH ERROR:", e)

def build_keyboard(user_id):

    data = search_cache[user_id]
    results = data["results"]
    page = data["page"]

    start = page * 5
    end = start + 5
    current_tracks = results[start:end]

    buttons = []

    for i, entry in enumerate(current_tracks):
        title = entry.get("title", "Без названия")
        buttons.append([
            InlineKeyboardButton(
                text=title[:50],
                callback_data=f"track_{start + i}"
            )
        ])

    nav_buttons = []

    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️", callback_data="prev_page")
        )

    if end < len(results):
        nav_buttons.append(
            InlineKeyboardButton(text="➡️", callback_data="next_page")
        )

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.callback_query(F.data == "next_page")
async def next_page(callback: CallbackQuery):

    user_id = callback.from_user.id

    if user_id not in search_cache:
        await callback.answer("Поиск устарел", show_alert=True)
        return

    data = search_cache[user_id]

    if (data["page"] + 1) * 5 >= len(data["results"]):
        await callback.answer("Это последнее окно", show_alert=True)
        return

    data["page"] += 1

    await callback.message.edit_reply_markup(
        reply_markup=build_keyboard(user_id)
    )

    await callback.answer()


@dp.callback_query(F.data == "prev_page")
async def prev_page(callback: CallbackQuery):

    user_id = callback.from_user.id

    if user_id not in search_cache:
        await callback.answer("Поиск устарел", show_alert=True)
        return

    data = search_cache[user_id]

    if data["page"] == 0:
        await callback.answer("Это первое окно", show_alert=True)
        return

    data["page"] -= 1

    await callback.message.edit_reply_markup(
        reply_markup=build_keyboard(user_id)
    )

    await callback.answer()

# ===== ОБРАБОТКА ВЫБОРА =====
@dp.callback_query(F.data.startswith("track_"))
async def download_track(callback: CallbackQuery):

    await callback.answer()

    user_id = callback.from_user.id

    if not check_limit(user_id):
        await callback.message.answer(
            "Вы достигли лимита.\n\nБесплатно: 3 трека в день\nПремиум: 10 треков в день"
        )
        return

    if user_id not in search_cache:
        await callback.message.answer("Поиск устарел")
        return

    index = int(callback.data.split("_")[1])
    results = search_cache[user_id]["results"]

    if index >= len(results):
        await callback.message.answer("Трек недоступен")
        return

    entry = results[index]
    url = entry["url"]
    title = entry.get("title", "Track")

    # ===== RAM
    if url in track_cache:
        await callback.message.answer_audio(
            audio=track_cache[url],
            caption='Скачать трек [здесь](https://t.me/ElizCityBot)',
            parse_mode="Markdown"
        )
        increase_usage(user_id, url)
        return

    # ===== БД
    cursor.execute("SELECT file_id FROM tracks WHERE youtube_url = ?", (url,))
    row = cursor.fetchone()

    if row:
        file_id = row[0]
        track_cache[url] = file_id

        await callback.message.answer_audio(
            audio=file_id,
            caption='Скачать трек [здесь](https://t.me/ElizCityBot)',
            parse_mode="Markdown"
        )
        increase_usage(user_id, url)
        return

    # ===== СКАЧИВАНИЕ
    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": f"{DOWNLOAD_PATH}/%(title)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": 30_000_000,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
    }

    if platform.system() == "Windows":
        ydl_opts["ffmpeg_location"] = "C:/ffmpeg/bin"

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"
    except Exception as e:
        print("DOWNLOAD ERROR:", e)
        await callback.message.answer("Ошибка загрузки")
        return

    try:
        from aiogram.types import FSInputFile

        audio = FSInputFile(file_path)

        msg = await callback.message.answer_audio(
            audio=audio,
            caption='Скачать трек [здесь](https://t.me/ElizCityBot)',
            parse_mode="Markdown",
            title=title
        )
    except Exception as e:
        print("SEND AUDIO ERROR:", e)
        await callback.message.answer("Ошибка отправки")
        return

    file_id = msg.audio.file_id

    cursor.execute(
        "INSERT OR IGNORE INTO tracks (youtube_url, title, file_id) VALUES (?, ?, ?)",
        (url, title, file_id)
    )
    conn.commit()

    track_cache[url] = file_id
    increase_usage(user_id, url)

    if os.path.exists(file_path):
        os.remove(file_path)

from datetime import datetime, timedelta # Импорт для работы с датой и временем

def check_limit(user_id):

    # 🔥 Безлимит для админа
    if user_id in ADMIN_IDS:
        return True

    today = datetime.now().date()

    cursor.execute("SELECT daily_count, last_reset, premium_until FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute(
            "INSERT INTO users (user_id, daily_count, last_reset) VALUES (?, 0, ?)",
            (user_id, str(today))
        )
        conn.commit()
        return True

    daily_count, last_reset, premium_until = row

    # Сброс счетчика если новый день
    if last_reset != str(today):
        cursor.execute(
            "UPDATE users SET daily_count = 0, last_reset = ? WHERE user_id = ?",
            (str(today), user_id)
        )
        conn.commit()
        daily_count = 0

    # Проверка премиума
    if premium_until:
        if datetime.fromisoformat(premium_until) > datetime.now():
            limit = 10
        else:
            limit = 3
    else:
        limit = 3

    return daily_count < limit

conn.commit()

def increase_usage(user_id, url=None):

    cursor.execute(
        """
        UPDATE users
        SET daily_count = daily_count + 1,
            total_downloads = total_downloads + 1
        WHERE user_id = ?
        """,
        (user_id,)
    )

    if url:
        cursor.execute(
            """
            UPDATE tracks
            SET download_count = download_count + 1
            WHERE youtube_url = ?
            """,
            (url,)
        )

    conn.commit()

# ===== ЗАПУСК =====
async def warmup_cache():

    cursor.execute("""
        SELECT youtube_url, file_id
        FROM tracks
    """)

    rows = cursor.fetchall()

    for url, file_id in rows:
        track_cache[url] = file_id

    print(f"Cache warmed: {len(rows)} tracks loaded")

async def main():
    print("Bot started")

    await warmup_cache()

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())