import asyncio

from bot.config import bot
from bot.utils.bot_utils import clean_whatsapp_md, sync_to_async
from bot.utils.chatbot_utils import chat_bot
from bot.utils.log_utils import logger
from bot.utils.msg_utils import function_dict


async def chat(event, _, client):
    try:
        if event.chat.is_group:
            return
        if bot.client.me.JID.User == event.from_user.id:
            return
        if not (text := event.text):
            return
        if text.split()[0] in function_dict:
            return
        text = clean_whatsapp_md(text)
        response = await sync_to_async(chat_bot.get_response, text)
        await asyncio.sleep(1)
        await event.reply(str(response))
    except Exception:
        await logger(Exception)


def add_chatbot_handler():
    if not chat_bot:
        return
    bot.add_handler(chat)
