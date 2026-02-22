from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 31635604
api_hash = "8fff8b47522a2c5aae7e905aab975683"

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print(client.session.save())