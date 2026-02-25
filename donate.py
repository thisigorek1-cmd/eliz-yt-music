# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery,
    Message
)

from database import get_sql
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import os
from aiogram.types import FSInputFile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DONATE_PHOTO = os.path.join(BASE_DIR, "assets", "donate.jpg")

def donate_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Premium 2 недели — 10 ⭐", callback_data="donate_2w")],
            [InlineKeyboardButton(text="Premium 1 месяц — 20 ⭐", callback_data="donate_1m")],
            [InlineKeyboardButton(text="Premium 2 месяца — 40 ⭐", callback_data="donate_2m")],
            [InlineKeyboardButton(text="Premium 3 месяца — 50 ⭐", callback_data="donate_3m")],
            [InlineKeyboardButton(text="Premium 1 год — 200 ⭐", callback_data="donate_1y")],
            [InlineKeyboardButton(text="💛 Поддержка проекта — 2 ⭐", callback_data="donate_support")]
        ]
    )

router = Router()

# =========================
# ТАРИФЫ
# =========================
DONATE_PLANS = {
    "donate_2w": {
        "title": "Premium 2 недели",
        "stars": 10,
        "days": 14
    },
    "donate_1m": {
        "title": "Premium 1 месяц",
        "stars": 20,
        "days": 30
    },
    "donate_2m": {
        "title": "Premium 2 месяца",
        "stars": 40,
        "days": 60
    },
    "donate_3m": {
        "title": "Premium 3 месяца",
        "stars": 50,
        "days": 90
    },
    "donate_1y": {
        "title": "Premium 1 год",
        "stars": 200,
        "days": 365
    },
    "donate_support": {
        "title": "Поддержка проекта",
        "stars": 2,
        "days": 0
    }
}

@router.message(F.text == "Донат 🍩", F.chat.type == "private")
async def donate_menu(message: Message):

    photo = FSInputFile(DONATE_PHOTO)

    await message.answer_photo(
        photo=photo,
        caption=(
            "💎 <b>Premium подписка</b>\n\n"
            "🎵 <b>Бесплатный пакет:</b>\n"
            "• 3 трека в день\n\n"
            "⭐ <b>Premium пакет:</b>\n"
            "• 10 треков в день\n"
            "• Отключение рекламы\n\n"
            "👇 Выберите пакет ниже:"
        ),
        reply_markup=donate_keyboard(),
        parse_mode="HTML"
    )

# =========================
# СОЗДАНИЕ INVOICE
# =========================
@router.callback_query(F.data.startswith("donate_"))
async def create_invoice(call: CallbackQuery, bot: Bot):

    plan_key = call.data

    if plan_key not in DONATE_PLANS:
        await call.answer("Ошибка тарифа")
        return

    plan = DONATE_PLANS[plan_key]

    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=plan["title"],
        description=f"Оплата {plan['title']}",
        provider_token="",   # для Stars оставить пустым
        currency="XTR",
        prices=[LabeledPrice(
            label=plan["title"],
            amount=plan["stars"]
        )],
        payload=plan_key
    )

    await call.answer()

# =========================
# PRE CHECKOUT
# =========================
@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# =========================
# УСПЕШНАЯ ОПЛАТА
# =========================
@router.message(F.successful_payment)
async def successful_payment(message: Message):

    payload = message.successful_payment.invoice_payload

    if payload not in DONATE_PLANS:
        return

    plan = DONATE_PLANS[payload]
    user_id = message.from_user.id

    if plan["days"] == 0:
        await message.answer("💛 Спасибо за поддержку проекта!")
        return

    conn = get_sql()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT premium_until FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()

    now = datetime.now()

    if row and row[0]:
        current_until = datetime.fromisoformat(row[0])
        if current_until > now:
            new_until = current_until + timedelta(days=plan["days"])
        else:
            new_until = now + timedelta(days=plan["days"])
    else:
        new_until = now + timedelta(days=plan["days"])

    cursor.execute("""
        INSERT INTO users (user_id, premium_until, daily_count, last_reset)
        VALUES (?, ?, 0, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET premium_until=excluded.premium_until
    """, (user_id, new_until.isoformat(), str(now.date())))

    conn.commit()
    conn.close()

    await message.answer(
        f"⭐ Премиум активирован!\n\n"
        f"Действует до: {new_until.strftime('%d.%m.%Y')}"
    )

def register_donate_handlers(dp, bot):
    dp.include_router(router)