import asyncio
import pickle

from bot import bot, msg_store_file, msg_store_lock
from bot.utils.bot_utils import sync_to_async
from bot.utils.log_utils import logger
from bot.utils.os_utils import file_exists, size_of


class Message_store:
    """A class for locally storing messages"""

    def __init__(self):
        self.msg_limit = 50
        if not (file_exists(msg_store_file) and size_of(msg_store_file) > 0):
            with open(msg_store_file, "wb") as file:
                pickle.dump({}, file)

    def _get_message(self, chat_id, msg_id):
        if not (message_store := self._get_message_store()):
            return
        messages = message_store.get(chat_id)
        if not messages:
            return
        for msg in messages:
            if msg.id == msg_id:
                return msg

    def _get_message_store(self):
        if file_exists(msg_store_file) and size_of(msg_store_file) > 0:
            with open(msg_store_file, "rb") as file:
                message_store = pickle.load(file)
        else:
            message_store = {}
        return message_store

    def _get_messages(self, chat_id):
        if not (message_store := self._get_message_store()):
            return
        return message_store.get(chat_id)

    def _patch(self, *messages):
        patched_messages = []
        for message in messages:
            message.client = bot.client
            if message.reply_to_message:
                message.reply_to_message.client = bot.client
            patched_messages.append(message)
        return patched_messages

    def _save(self, *messages):
        message_store = self._get_message_store()
        for message in messages:
            message.client = None
            if message.reply_to_message:
                message.reply_to_message.client = None
            message_store.setdefault(message.chat.id, []).append(message)
            while len(message_store.get(message.chat.id)) > self.msg_limit:
                message_store.setdefault(message.chat.id, []).pop()
        with open(msg_store_file, "wb") as file:
            pickle.dump(message_store, file)

    # AIO
    async def get_messages(self, chat_id):
        bot.force_save_messages = True
        async with msg_store_lock:
            return await sync_to_async(self._get_messages, chat_id)

    async def get_message(self, chat_id, msg_id):
        bot.force_save_messages = True
        async with msg_store_lock:
            return await sync_to_async(self._get_message, chat_id, msg_id)

    async def save(self, *messages):
        bot.force_save_messages = True
        async with msg_store_lock:
            return await sync_to_async(self._save, *messages)


msg_store = Message_store()


async def auto_save_msg():
    while True:
        try:
            if messages := bot.pending_saved_messages:
                async with msg_store_lock:
                    try:
                        while len(messages) < 5 and not bot.force_save_messages:
                            await asyncio.sleep(1)
                        await sync_to_async(msg_store._save, *messages)
                    except Exception:
                        await logger(Exception)
                    finally:
                        messages.clear()
                        if bot.force_save_messages:
                            bot.force_save_messages = False
                await asyncio.sleep(1)
        except Exception:
            await logger(Exception)
            await asyncio.sleep(60)
