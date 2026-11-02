import asyncio
from types import SimpleNamespace

from neonize.utils.jid import build_jid

from bot.config import bot, conf
from bot.utils.genshin_utils import GenshinWatcher, fetch_codes, format_code
from bot.utils.msg_utils import (
    chat_is_allowed,
    user_is_admin,
    user_is_allowed,
    user_is_privileged,
)

watcher = GenshinWatcher(".local_genshin_codes.json")


def _chat_is_allowed(chat):
    if not bot.is_connected or bot.paused or bot.offline:
        return False
    user, _, server = chat.partition("@")
    if not user or server not in {"g.us", "s.whatsapp.net", "lid"}:
        return False
    event = SimpleNamespace(chat=SimpleNamespace(id=user, is_group=server == "g.us"))
    return chat_is_allowed(event)


async def _send_code(chat, text):
    user, _, server = chat.partition("@")
    await bot.client.send_message(build_jid(user, server), text, link_preview=False)


def start_genshin_watcher():
    watcher.start(_send_code, _chat_is_allowed)


async def stop_genshin_watcher():
    await watcher.stop()


async def genshin_handler(event, args, client):
    """
    Watch for new Genshin Impact redeem codes in this chat.
    Arguments:
        on - Subscribe (group admin, owner or sudo in groups).
        off - Stop updates (group admin, owner or sudo in groups).
        codes - Show currently listed codes.

    Checks run every 15-60 minutes. Existing codes are remembered when enabling
    updates, and posted codes are remembered across restarts.
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event) or not user_is_allowed(user):
            return
    action = args.strip().casefold()
    if action in {"on", "off"} and event.chat.is_group:
        if not user_is_privileged(user):
            group = await client.get_group_info(event.chat.jid)
            if not user_is_admin(user, group.Participants):
                return await event.reply(
                    "Only group admins can change Genshin updates."
                )
    chat = f"{event.chat.id}@{event.chat.server}"
    try:
        if action == "codes":
            codes = await asyncio.to_thread(fetch_codes)
            if not codes:
                return await event.reply(
                    "No active Genshin codes are listed right now."
                )
            for code in codes:
                await event.reply(format_code(code), quote=False, link_preview=False)
        elif action in {"on", "off"}:
            async with watcher.lock:
                if action == "on":
                    if chat not in watcher.store.chats:
                        codes = await asyncio.to_thread(fetch_codes)
                        watcher.store.subscribe(chat, codes)
                    text = "Genshin updates enabled. Checking every 15-60 minutes."
                else:
                    watcher.store.unsubscribe(chat)
                    text = "Genshin updates disabled for this chat."
            await event.reply(text)
        else:
            status = "on" if chat in watcher.store.chats else "off"
            pre = conf.CMD_PREFIX
            await event.reply(
                f"Genshin updates: {status}.\n"
                f"{pre}genshin on - watch for new codes\n"
                f"{pre}genshin off - stop updates\n"
                f"{pre}genshin codes - show current codes"
            )
    except Exception as exc:
        await event.reply(f"Could not check Genshin codes: {exc}")
