# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)

from database import get_sql
import os

router = Router()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DONATE_PHOTO = os.path.join(BASE_DIR, "assets", "donate.jpg")

STAR_PREFIX = "PREMIUM"
GIFT_PREFIX = "TG_GIFT"

# =====================================
# PREMIUM ТАРИФЫ
# =====================================
DONATE_PLANS = {
    "donate_2w": ("Premium 2 недели", 10, 14),
    "donate_1m": ("Premium 1 месяц", 20, 30),
    "donate_2m": ("Premium 2 месяца", 40, 60),
    "donate_3m": ("Premium 3 месяца", 50, 90),
    "donate_1y": ("Premium 1 год", 200, 365),
    "donate_support": ("Поддержка проекта", 2, 0),
}

# =====================================
# КНОПКИ
# =====================================
def donate_keyboard():
    kb = []

    for key, plan in DONATE_PLANS.items():
        kb.append([
            InlineKeyboardButton(
                text=f"{plan[0]} — {plan[1]} ⭐",
                callback_data=key
            )
        ])

    kb.append([
        InlineKeyboardButton(
            text="🎁 Магазин подарков",
            callback_data="open_gifts"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=kb)

# =====================================
# МЕНЮ ДОНАТА
# =====================================
@router.message(F.text == "Донат 🍩", F.chat.type == "private")
async def donate_menu(message: Message):

    photo = FSInputFile(DONATE_PHOTO)

    await message.answer_photo(
        photo,
        caption=(
            "💎 <b>Возможности ⭐ Premium</b>\n\n"
            "⭐ Premium убирает лимит на поиск треков\n"
            "✅ убирает рекламу\n\n"
            "👇 Выберите:"
        ),
        parse_mode="HTML",
        reply_markup=donate_keyboard()
    )

# =====================================
# 🎁 AUTO МАГАЗИН ПОДАРКОВ
# =====================================
@router.callback_query(F.data == "open_gifts")
async def open_gifts(call: CallbackQuery, bot: Bot):

    gifts = await bot.get_available_gifts()

    kb = []

    for g in gifts.gifts:

        emoji = "🎁"
        name = "Подарок"

        if getattr(g, "sticker", None):
            emoji = getattr(g.sticker, "emoji", "🎁")

        # авто название
        NAMES = {
            "💝": "Сердце",
            "🧸": "Мишка",
            "🎁": "Подарок",
            "🌹": "Роза",
            "🎂": "Торт",
            "💐": "Букет",
            "🚀": "Ракета",
            "🏆": "Кубок",
            "💍": "Кольцо",
            "💎": "Алмаз",
            "🍾": "Шампанское"
        }

        name = NAMES.get(emoji, "Подарок")

        kb.append([
            InlineKeyboardButton(
                text=f"{emoji} {name} — {g.star_count}⭐",
                callback_data=f"gift:{g.id}"
            )
        ])

    kb.append([
        InlineKeyboardButton(
            text="⬅ Назад",
            callback_data="back_donate"
        )
    ])

    await call.message.answer(
        "🎁 <b>Магазин подарков</b>\n\nВыберите подарок:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

    await call.answer()

# =====================================
# СОЗДАНИЕ INVOICE GIFT
# =====================================
@router.callback_query(F.data.startswith("gift:"))
async def gift_invoice(call: CallbackQuery, bot: Bot):

    gift_id = call.data.split(":")[1]

    gifts = await bot.get_available_gifts()

    price = 15
    emoji = "🎁"

    for g in gifts.gifts:
        if str(g.id) == gift_id:
            price = g.star_count
            if getattr(g, "sticker", None):
                emoji = g.sticker.emoji
            break

    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"{emoji} Telegram подарок",
        description="Подарок появится в профиле",
        currency="XTR",
        prices=[LabeledPrice(
            label="Telegram Gift",
            amount=price
        )],
        provider_token="",
        payload=f"{GIFT_PREFIX}:{gift_id}"
    )

    await call.answer()

# =====================================
# PREMIUM INVOICE
# =====================================
@router.callback_query(F.data.startswith("donate_"))
async def create_invoice(call: CallbackQuery, bot: Bot):

    await call.answer()

    title, stars, _ = DONATE_PLANS[call.data]

    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=title,
        description=title,
        currency="XTR",
        provider_token="",
        prices=[
            LabeledPrice(
                label=title,
                amount=stars
            )
        ],
        payload=f"{STAR_PREFIX}:{call.data}"
    )

# =====================================
# PRE CHECKOUT
# =====================================
@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(q.id, ok=True)

# =====================================
# УСПЕШНАЯ ОПЛАТА
# =====================================
@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot):

    payload = message.successful_payment.invoice_payload
    uid = message.from_user.id

    # ========= GIFT =========
    if payload.startswith(GIFT_PREFIX):

        gift_id = payload.split(":")[1]

        await message.answer("🎁 Отправляем подарок...")

        await bot.send_gift(
            user_id=uid,
            gift_id=gift_id
        )

        await message.answer(
            "✅ Подарок отправлен в профиль!"
        )
        return

    # ========= PREMIUM =========
    if payload.startswith(STAR_PREFIX):

        key = payload.split(":")[1]
        title, _, days = DONATE_PLANS[key]

        if days == 0:
            await message.answer("💛 Спасибо за поддержку!")
            return

        conn = get_sql()
        cur = conn.cursor()

        now = datetime.now()

        # получаем текущий premium
        cur.execute(
            "SELECT premium_until FROM users WHERE user_id=?",
            (uid,)
        )
        row = cur.fetchone()

        if row and row[0]:
            current_until = datetime.fromisoformat(row[0])

            # если ещё активен → плюсуем
            if current_until > now:
                new_until = current_until + timedelta(days=days)
            else:
                new_until = now + timedelta(days=days)
        else:
            new_until = now + timedelta(days=days)


        cur.execute("""
        INSERT INTO users(user_id,premium_until)
        VALUES(?,?)
        ON CONFLICT(user_id)
        DO UPDATE SET premium_until=excluded.premium_until
        """, (
            uid,
            new_until.isoformat()
        ))

        conn.commit()
        conn.close()

        await message.answer(
            f"⭐ Premium активирован!\n"
            f"До {new_until.strftime('%d.%m.%Y')}"
        )


# =====================================
# REGISTER ROUTER
# =====================================

def register_donate_handlers(dp, bot):
    dp.include_router(router)

        