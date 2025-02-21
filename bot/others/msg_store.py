import asyncio
import pickle
from copy import deepcopy

from bot import bot, conf, msg_store_file, msg_store_lock
from bot.utils.bot_utils import sync_to_async
from bot.utils.db_utils import save2db2
from bot.utils.log_utils import log, logger
from bot.utils.os_utils import file_exists, size_of


class Message_store:
    """A class for locally storing messages"""

    def __init__(self):
        self.msg_limit = conf.MAX_SAVED_MESSAGES
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
        message_store = {}
        try:
            if file_exists(msg_store_file) and size_of(msg_store_file) > 0:
                with open(msg_store_file, "rb") as file:
                    message_store = pickle.load(file)
        except EOFError:
            log(e="Message_store local database has been destroyed.")
            log(e="Rebuilding…")
            with open(msg_store_file, "wb") as file:
                pickle.dump({}, file)
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
            message_store.setdefault(message.chat.id, []).append(deepcopy(message))
            while len(message_store.get(message.chat.id)) > self.msg_limit:
                message_store.setdefault(message.chat.id, []).pop(0)
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
    bot.auto_save_msg_is_running = True
    while True:
        if messages := bot.pending_saved_messages:
            async with msg_store_lock:
                try:
                    while len(messages) < 15 and not bot.force_save_messages:
                        await asyncio.sleep(1)
                    await sync_to_async(msg_store._save, *messages)
                    if bot.msg_leaderboard_counter > 10:
                        await save2db2(bot.group_dict, "groups")
                        bot.msg_leaderboard_counter = 0
                except Exception:
                    await logger(Exception)
                finally:
                    messages.clear()
                    if bot.force_save_messages:
                        bot.force_save_messages = False
            await asyncio.sleep(1)
        await asyncio.sleep(3)
