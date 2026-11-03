from inspect import getdoc

from bot.config import bot
from bot.utils.bot_utils import list_to_str
from bot.utils.db_utils import save2db2
from bot.utils.gift_utils import fetch_codes, get_msg_from_codes
from bot.utils.log_utils import logger
from bot.utils.msg_utils import chat_is_allowed, user_is_allowed, user_is_privileged


async def manage_autogift_chat(event, args):
    if not user_is_privileged(event.from_user.id):
        return await event.react("🚫")
    try:
        action, _, chat = args.strip().partition(" ")
        chat = chat.strip()
        chats = bot.gift_dict["chats"]
        if action == "-get":
            if not chats:
                return await event.reply("*No chat set!*")
            return await event.reply(
                list_to_str([c or "default" for c in chats], sep=", ")
            )
        if action not in ("-add", "-rm") or not chat:
            return await event.reply(getdoc(gift_codes))
        if chat == ".":
            chat = f"{event.chat.id}:{event.chat.server}"
        elif chat.casefold() == "default":
            chat = None
        if action == "-add":
            if chat in chats:
                return await event.reply("*Chat already added!*")
            chats.append(chat)
        else:
            if chat not in chats:
                return await event.reply("*Given chat was never added!*")
            chats.remove(chat)
        await save2db2(bot.gift_dict, "gift")
        done = "added" if action == "-add" else "removed"
        await event.reply(f"*{chat or 'default'}* has been {done}.")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def gift_codes(event, args, client):
    """
    Fetches the latest Genshin Impact redeem codes.
    Uses hoyo-codes.seria.moe, or api.ennead.cc when that's down.

    Arguments:
        -add <chat> : [Owner | Sudo] post new codes to a chat automatically
        -rm <chat> : [Owner | Sudo] stop posting new codes to a chat
        -get : [Owner | Sudo] list the chats new codes are posted to
    chat: . for this chat, default for RSS_CHAT, or chat_id:server
    New codes are checked for every 30 minutes.
    """
    if args:
        return await manage_autogift_chat(event, args)
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    status = None
    try:
        status = await event.reply("*Fetching latest giftcodes…*")
        codes = await fetch_codes()
        await event.reply(
            get_msg_from_codes(codes) if codes else "*No active codes right now.*"
        )
        await status.delete()
    except Exception:
        await logger(Exception)
        await event.react("❌")
        if status:
            await status.edit("*Couldn't fetch the codes right now.*")
