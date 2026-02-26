import asyncio
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    FSInputFile,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN
from database import init_db
from music import register_music_handlers, tg_user, warmup_cache
from donate import register_donate_handlers
from auto_top import scheduler
from admin import router as admin_router

# ===== КНОПКИ =====
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Профиль 👤")],
            [KeyboardButton(text="Донат 🍩")]
        ],
        resize_keyboard=True
    )

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_PHOTO = os.path.join(BASE_DIR, "assets", "profile.jpg")

async def main():
    print("Bot started")

    init_db()

    session = AiohttpSession()
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher()

    # ===== /start =====
    @dp.message(CommandStart())
    async def start_handler(message: Message):
        await message.answer(
            "🎵 <b>Привет, я Eliz Music!</b>\n\n"
            "Найду тебе любой трек с YouTube.\n"
            "Просто напиши название трека — и я отправлю его 🚀",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )

    # ===== ПРОФИЛЬ =====
    from database import get_sql

    @dp.message(F.text == "Профиль 👤", F.chat.type == "private")
    async def profile_handler(message: Message):

        user_id = message.from_user.id
        name = message.from_user.first_name
        today = datetime.now().date()

        conn = get_sql()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT daily_count, last_reset, premium_until, total_downloads FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()

        if not row:
            cursor.execute(
                "INSERT INTO users (user_id, daily_count, last_reset, total_downloads) VALUES (?, 0, ?, 0)",
                (user_id, str(today))
            )
            conn.commit()
            daily_count = 0
            premium_until = None
            total_downloads = 0
        else:
            daily_count, last_reset, premium_until, total_downloads = row

        if row and last_reset != str(today):
            cursor.execute(
                "UPDATE users SET daily_count = 0, last_reset = ? WHERE user_id = ?",
                (str(today), user_id)
            )
            conn.commit()
            daily_count = 0

        remaining_text = ""

        if premium_until:
            premium_date = datetime.fromisoformat(premium_until)
            now = datetime.now()

            if premium_date > now:
                status = "Premium 👑"
                limit_text = "♾️"

                days_left = (premium_date.date() - now.date()).days
                remaining_text = f"\n\n⏳ До конца Premium осталось: {days_left} д."
            else:
                status = "Бесплатный"
                limit_text = f"{daily_count}/3"
        else:
            status = "Бесплатный"
            limit_text = f"{daily_count}/3"

        conn.close()

        photo = FSInputFile(PROFILE_PHOTO)

        await message.answer_photo(
            photo=photo,
            caption=(
                f"👥 <b>Ваш профиль</b>\n\n"
                f"🥷🏻 Имя: {name}\n"
                f"🆔 ID: {user_id}\n\n"
                f"📌 Статус: {status}\n"
                f"🎵 лимит треков сегодня {limit_text}\n\n"
                f"🔥 Всего треков найдено вами: {total_downloads}"
                f"{remaining_text}"
            ),
            parse_mode="HTML"
        )

    # ===== РЕГИСТРАЦИЯ МОДУЛЕЙ =====
    register_music_handlers(dp, bot)
    register_donate_handlers(dp, bot)

    dp.include_router(admin_router)

    await warmup_cache()
    await tg_user.start()

    asyncio.create_task(scheduler())

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await tg_user.disconnect()


if __name__ == "__main__":
    asyncio.run(main())