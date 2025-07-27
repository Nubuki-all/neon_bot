import asyncio

from bot.config import bot
from bot.utils.bot_utils import sync_to_async
from bot.utils.chatbot_utils import chat_bot
from bot.utils.log_utils import logger
from bot.utils.msg_utils import function_dict


async def chat(event, _, client):
    try:
        if not (text := event.text):
            return
        if event.chat.is_group:
            return
        if text in function_dict:
            return
        response = await sync_to_async(chat_bot.get_response, text)
        await asyncio.sleep(1)
        await event.reply(response)
    except Exception:
        await logger(Exception)


def add_chatbot_handler():
    if not chat_bot:
        return
    bot.add_handler(chat)
