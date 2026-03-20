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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import InputMediaPhoto
from donate import register_donate_handlers
from auto_top import scheduler
from admin import router as admin_router

# ===== КНОПКИ =====
def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
            ]

        ]
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
    from database import get_sql

    @dp.message(CommandStart())
    async def start_handler(message: Message):

        user_id = message.from_user.id
        today = datetime.now().date()

        conn = get_sql()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

        if not user:
            cursor.execute(
                "INSERT INTO users (user_id, daily_count, last_reset, total_downloads) VALUES (?, 0, ?, 0)",
                (user_id, str(today))
            )
            conn.commit()

            print(f"NEW USER: {user_id}")

        conn.close()

        photo = FSInputFile("assets/profile.jpg")

        await message.answer_photo(
            photo=photo,
            caption=(
                "🎵 <b>Eliz Music</b>\n\n"
                "Найду тебе любой трек 🎧\n"
                "Просто напиши название"
            ),
            reply_markup=main_menu(),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data == "profile")
    async def profile_menu(call):

        user_id = call.from_user.id
        name = call.from_user.first_name
        today = datetime.now().date()

        conn = get_sql()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT daily_count, last_reset, premium_until, total_downloads FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()

        if not row:
            daily_count = 0
            premium_until = None
            total_downloads = 0
        else:
            daily_count, last_reset, premium_until, total_downloads = row

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

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🍩 Донат", callback_data="donate_1m")],
                [InlineKeyboardButton(text="🛠 Support", url="https://t.me/elizsupport_bot")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
            ]
        )

        photo = FSInputFile(PROFILE_PHOTO)

        await call.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
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
            ),
            reply_markup=kb
        )

        await call.answer()

    @dp.callback_query(F.data == "donate")
    async def donate_menu(call):

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Купить Premium", callback_data="buy_premium")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="profile")]
            ]
        )

        await call.message.edit_caption(
            caption=(
                "🍩 <b>Донат</b>\n\n"
                "👑 Premium — без лимитов\n"
                "⚡ Быстрая загрузка\n\n"
                "Выбери действие:"
            ),
            reply_markup=kb,
            parse_mode="HTML"
        )

        await call.answer()

    @dp.callback_query(F.data == "back")
    async def back(call):

        photo = FSInputFile("assets/profile.jpg")

        await call.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=(
                    "🎵 <b>Eliz Music</b>\n\n"
                    "Найду тебе любой трек 🎧\n"
                    "Просто напиши название"
                ),
                parse_mode="HTML"
            ),
            reply_markup=main_menu()
        )

        await call.answer()

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