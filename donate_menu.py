from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def donate_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Купить премиум - 25 ⭐️",
                    callback_data="buy_premium"
                )
            ]
        ]
    )