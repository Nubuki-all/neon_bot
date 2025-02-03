import asyncio
import pickle
from bot import bot, conf, msg_store_file, msg_store_lock

from bot.utils.bot_utils import sync_to_async
from bot.utils.os_utils import file_exists


class Message_store:
    """A class for locally storing messages"""
    def __init__(self):
        self.msg_limit = 50
        if not file_exists(msg_store_file):
            with open(msg_store_file, "wb") as file:
                pickle.dump({}, file)
    def _get_messages(self, chat_id):
        with open(msg_store_file, "rb") as file:
            messages = pickle.load(file)
        return messages.get(chat_id)
    def _get_message(self, chat_id, msg_id):
        with open(msg_store_file, "rb") as file:
            message_store = pickle.load(file)
        messages = message_store.get(chat_id)
        if not messages:
            return
        for msg in messages:
            if msg.id == msg_id:
                return msg
    def _save(self, *msg):
        with open(msg_store_file, "rb") as file:
            message_store = pickle.load(file)
        message_store.setdefault(msg.chat.id, []). extend(msg)
        while len(message_store.get(msg.chat.id)) > self.msg_limit:
            message_store.setdefault(msg.chat.id, []).pop()
        with open(msg_store_file, "wb") as file:
            pickle.dump(message_store, file)

    # AIO
    async def get_messages(self, chat_id):
        async with msg_store_lock:
            bot.force_save_messages = True
            return await sync_to_async(self._get_messages, chat_id)
    async def get_message(self, chat_id, msg_id):
        async with msg_store_lock:
            bot.force_save_messages = True
            return await sync_to_async(self._get_message, chat_id, msg_id)
    async def save(self, *msg):
        async with msg_store_lock:
            bot.force_save_messages = True
            return await sync_to_async(self._save, *msg)

msg_store = Message_store()

async def auto_save_msg():
    while True:
        if messages := bot.pending_saved_messages:
            async with msg_store_lock:
                while len(messages) < 5 and not bot.force_save_messages:
                    await asyncio.sleep(1)
                await msg_store.save(*messages)
                messages.clear()
                if bot.force_save_messages:
                    bot.force_save_messages = False
            await asyncio.sleep(1)

