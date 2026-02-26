# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ChatType
from aiogram import Router, F, Bot
from database import get_sql

ADMIN_ID = 8454715718

router = Router()

# =========================
# КНОПКИ
# =========================
def admin_panel_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [
                InlineKeyboardButton(text="🚫 Бан", callback_data="admin_ban"),
                InlineKeyboardButton(text="✅ Разбан", callback_data="admin_unban"),
            ],
            [
                InlineKeyboardButton(text="⭐ Выдать премиум", callback_data="admin_premium_add"),
                InlineKeyboardButton(text="❌ Забрать премиум", callback_data="admin_premium_remove"),
            ]
        ]
    )

# =========================
# /aura — вход в админку
# =========================
@router.message(Command("aura"))
async def open_admin_panel(message: Message):

    if message.chat.type != ChatType.PRIVATE:
        return

    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "🔐 <b>Админ панель</b>",
        reply_markup=admin_panel_kb(),
        parse_mode="HTML"
    )

# =========================
# СТАТИСТИКА
# =========================
@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):

    if call.from_user.id != ADMIN_ID:
        return

    conn = get_sql()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE premium_until IS NOT NULL"
    )
    premium_users = cursor.fetchone()[0]

    conn.close()

    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"⭐ Активный премиум: <b>{premium_users}</b>"
    )

    await call.message.edit_text(text, parse_mode="HTML")
    await call.answer()

# =========================
# РЕЖИМЫ
# =========================
ADMIN_MODE = None  # ban / unban / premium_add / premium_remove

@router.callback_query(F.data == "admin_ban")
async def ask_ban(call: CallbackQuery):
    global ADMIN_MODE
    if call.from_user.id != ADMIN_ID:
        return
    ADMIN_MODE = "ban"
    await call.message.answer("Введите ID пользователя для бана:")
    await call.answer()


@router.callback_query(F.data == "admin_unban")
async def ask_unban(call: CallbackQuery):
    global ADMIN_MODE
    if call.from_user.id != ADMIN_ID:
        return
    ADMIN_MODE = "unban"
    await call.message.answer("Введите ID пользователя для разбана:")
    await call.answer()


@router.callback_query(F.data == "admin_premium_add")
async def ask_premium_add(call: CallbackQuery):
    global ADMIN_MODE
    if call.from_user.id != ADMIN_ID:
        return
    ADMIN_MODE = "premium_add"
    await call.message.answer("Введите ID пользователя для выдачи премиума:")
    await call.answer()


@router.callback_query(F.data == "admin_premium_remove")
async def ask_premium_remove(call: CallbackQuery):
    global ADMIN_MODE
    if call.from_user.id != ADMIN_ID:
        return
    ADMIN_MODE = "premium_remove"
    await call.message.answer("Введите ID пользователя для снятия премиума:")
    await call.answer()

# =========================
# ОБРАБОТКА ID
# =========================
@router.message(F.text.regexp(r"^\d+$"))
async def process_admin_id(message: Message, bot: Bot):

    global ADMIN_MODE

    if message.from_user.id != ADMIN_ID:
        return

    if message.chat.type != ChatType.PRIVATE:
        return

    if not ADMIN_MODE:
        return

    uid = int(message.text)

    conn = get_sql()
    cursor = conn.cursor()

    # Создаём пользователя если его нет
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, daily_count) VALUES (?, 0)",
        (uid,)
    )
    conn.commit()

    conn = get_sql()
    cursor = conn.cursor()

    # ===== БАН =====
    if ADMIN_MODE == "ban":
        cursor.execute("UPDATE users SET banned=1 WHERE user_id=?", (uid,))
        conn.commit()
        await message.answer(f"🚫 Пользователь {uid} забанен")

    # ===== РАЗБАН =====
    elif ADMIN_MODE == "unban":
        cursor.execute("UPDATE users SET banned=0 WHERE user_id=?", (uid,))
        conn.commit()
        await message.answer(f"✅ Пользователь {uid} разбанен")

    # ===== ВЫДАТЬ ПРЕМИУМ =====
    elif ADMIN_MODE == "premium_add":
        premium_until = datetime.now() + timedelta(days=30)

        cursor.execute(
            "UPDATE users SET premium_until=? WHERE user_id=?",
            (premium_until.isoformat(), uid)
        )
        conn.commit()

        await message.answer(f"⭐ Премиум выдан пользователю {uid}")

        try:
            await bot.send_message(
                uid,
                "🎁 <b>Поздравляем!</b>\n\n"
                "Вам активировали <b>Premium 👑</b>\n\n"
                "📅 Срок: 30 дней\n"
                "🎵 Лимит: ♾️ треков в день\n"
                "🚫 Без рекламы\n\n"
                "Спасибо, что пользуетесь Eliz Music 💙",
                parse_mode="HTML"
            )
        except Exception as e:
            print("Notify error:", e)

    # ===== СНЯТЬ ПРЕМИУМ =====
    elif ADMIN_MODE == "premium_remove":
        cursor.execute(
            "UPDATE users SET premium_until=NULL WHERE user_id=?",
            (uid,)
        )
        conn.commit()
        await message.answer(f"❌ Премиум снят у пользователя {uid}")

    conn.close()
    ADMIN_MODE = None

# =========================
# РЕГИСТРАЦИЯ
# =========================
def register_admin_handlers(dp):
    dp.include_router(router)