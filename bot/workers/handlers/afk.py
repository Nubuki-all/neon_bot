import asyncio
import time

from bot import jid
from bot.config import bot
from bot.others.msg_store import msg_store
from bot.utils.bot_utils import time_formatter
from bot.utils.db_utils import save2db2
from bot.utils.log_utils import logger
from bot.utils.msg_utils import (
    chat_is_allowed,
    construct_msg_and_evt,
    get_afk_status,
    get_mentioned,
    get_user_info,
    user_is_allowed,
    user_is_privileged,
)

afk_message = "*{0} is currently AFK!*\n\n*Reason:*\n> {1}\n\n*Since:* _{2}_ ago."

unafk_message = "*Welcome back, {0}.*\nYou were AFK for: *{1}*"


async def afk_helper(event, args, client):
    """
    Helper for AFK!
    """
    try:
        if not event.chat.is_group:
            return
        if not chat_is_allowed(event):
            return
        if afk_dict := get_afk_status(event.from_user.id):
            if afk_dict.get("grace"):
                afk_dict["grace"] = False
                bot.user_dict.setdefault(event.from_user.id, {}).update(afk=afk_dict)
                return await save2db2(bot.user_dict, "users")
            since = time_formatter(time.time() - afk_dict.get("time"))
            user_name = afk_dict.get("user_name")
            bot.user_dict.setdefault(event.from_user.id, {}).update(afk=False)
            await save2db2(bot.user_dict, "users")
            await event.reply(unafk_message.format(user_name, since))
        reped = []
        if (replied := event.reply_to_message) and (
            afk_dict := get_afk_status(replied.from_user.id)
        ):
            user = replied.from_user.id
            user_name = afk_dict.get("user_name")
            reason = afk_dict.get("reason")
            since = time_formatter(time.time() - afk_dict.get("time"))
            await event.reply(afk_message.format(user_name, reason, since))
            reply = await replied.reply(
                text=event.text, reply_privately=True, message=event.media
            )
            reply = construct_msg_and_evt(
                user, bot.me.JID.User, reply.id, event.text, Msg=event._message
            )
            await asyncio.sleep(1)
            await reply.reply(
                f"*@{event.from_user.id} replied to your message while you were AFK!*"
            )
        mentioned_users = get_mentioned(event.text or event.caption or str())
        while mentioned_users:
            user = mentioned_users[0]
            if user in reped:
                mentioned_users.pop(0)
                continue
            if not (afk_dict := get_afk_status(user)):
                mentioned_users.pop(0)
                continue
            if replied and replied.from_user.id == user:
                mentioned_users.pop(0)
                continue
            user_jid = jid.build_jid(user)
            user_name = afk_dict.get("user_name")
            reason = afk_dict.get("reason")
            since = time_formatter(time.time() - afk_dict.get("time"))
            await event.reply(afk_message.format(user_name, reason, since))
            if replied:
                rep = await bot.client.send_message(
                    user_jid, (replied.text or replied._message)
                )
                reply = construct_msg_and_evt(
                    user, bot.me.JID.User, rep.ID, replied.text, Msg=replied._message
                )
                await asyncio.sleep(1)
                rep = await reply.reply(text=event.text, message=event.media)
                rep_id = rep.id
            else:
                rep = await bot.client.send_message(
                    user_jid, (event.text or event._message)
                )
                rep_id = rep.ID
            reply = construct_msg_and_evt(
                user, bot.me.JID.User, rep_id, event.text, Msg=event._message
            )
            reped.append(user)
            await asyncio.sleep(1)
            await reply.reply(f"*@{event.from_user.id} tagged you while you were AFK!*")
            mentioned_users.pop(0)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def activate_afk(event, args, client):
    """
    Marks you as AFK;
    while AFK I will send, messages that either tags or mentions you to your DM
    Arguments:
    - [Optional] Your reason for being AFK
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if get_afk_status(user):
            return
        if not await msg_store.get_messages(user):
            return await event.reply(
                "*Kindly send me 'Hi' in Dm/Pm in order for you to be able to use this command!*"
            )
        user_info = await get_user_info(user)
        afk_dict = {
            "grace": event.chat.is_group,
            "reason": args,
            "time": time.time(),
            "user_name": user_info.PushName,
        }
        bot.user_dict.setdefault(event.from_user.id, {}).update(afk=afk_dict)
        await save2db2(bot.user_dict, "users")
        await event.reply(f"{user_info.PushName} is now AFK!", quote=False)
    except Exception:
        await logger(Exception)
        await event.react("❌")
