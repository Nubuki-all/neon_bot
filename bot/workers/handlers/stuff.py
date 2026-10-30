from datetime import datetime as dt

from bot.config import conf
from bot.utils.bot_utils import get_date_from_ts
from bot.utils.log_utils import logger
from bot.utils.msg_utils import (
    chat_is_allowed,
    tag_admins,
    user_is_admin,
    user_is_allowed,
    user_is_privileged,
)


async def getcmds(event, args, client):
    """
    List the bot's main commands.
    Tools, fun and role commands are listed by tools, fun and roles.

    Arguments: None
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        pre = conf.CMD_PREFIX
        msg = f"""{pre}start - *Hi!*
{pre}ping - *Check if bot is alive*
{pre}afk - *Enable AFK mode*
{pre}anime - *Fetch anime info from anilist*
{pre}airing - *Fetch anime airing info from anilist*
{pre}insession - *Start an Ace Attorney objection session*
{pre}renderobj - *Render an objection session into a video*
{pre}werewolf - *Play a game of Werewolf*
{pre}fun - *Get fun commands*
{pre}tools - *Get tools commands*
{pre}roles - *Get commands for roles*
{pre}sudo - *[Owner] View/Modify sudoers*
{pre}pause - *[Owner] Pauses/Unpauses bot*
{pre}logs - *[Owner] Get bot logs*
{pre}ban - *[Owner | Sudo] Prevent a user from using bot*
{pre}unban - *[Owner | Sudo] Unban a user*
{pre}call - *[Owner | Sudo] Play replied audio or a link in a voice call (test)*
{pre}endcall - *[Owner | Sudo] Hang up the voice call*
{pre}rss - *[Owner | Sudo] Setup bot to auto post RSS feeds*
{pre}update - *[Owner | Sudo] Update & restarts bot*
{pre}restart - *[Owner | Sudo] Restarts bot*
{pre}ytdl_* - *[Owner | Sudo | Admin] Disables/Enables auto media download (anyone in PM)*
{pre}amr_* - *[Owner | Sudo | Admin] Disables/Enables Auto msg ranking*
{pre}mute - *[Owner | Sudo | Admin] Enables Auto deletion of a user's message*
{pre}enable_atd - *[Owner | Sudo | Admin] Enables Auto deletion of @all tags*
{pre}disable_atd - *[Owner | Sudo | Admin] Disables Auto deletion of @all tags*
{pre}disable - *[Owner | Sudo | Admin] Disable bot in a GC*
{pre}enable - *[Owner | Sudo | Admin] Enable bot in a GC*
{pre}del - *[Owner | Sudo | Admin] Delete the replied message*
{pre}gc_info - *[Owner | Sudo | Admin] Get group info*
{pre}bash - *[Owner | Dev] Run bash commands*
{pre}eval - *[Owner | Dev] Evaluate python code*

* expands to _ytdl_enable/ytdl_disable_
* expands to _amr_enable/amr_disable_"""
        await event.reply(msg)
    except Exception as e:
        await logger(Exception)
        return await event.reply(f"*Error:*\n{e}")


async def gc_info(event, args, client):
    """
    [Owner | Sudo | Admin] Show group info. Group only.
    Replies with the group owner, creation date, group id and a list of admins.

    Arguments: None
    """
    if not event.chat.is_group:
        return await event.react("🚫")
    try:
        group_info = await client.get_group_info(event.chat.jid)
        user = event.from_user.id
        if not user_is_privileged(user):
            if not user_is_admin(user, group_info.Participants):
                return await event.react("🚫")
        gc_owner = f"@{group_info.OwnerJID.User}" if group_info.OwnerJID.User else "MIA"
        tags = ""
        for tag in tag_admins(group_info.Participants).split():
            tags += f"- {tag}\n"
        tags = tags.rstrip("\n")
        return await event.reply(
            f"*Owner:* {gc_owner}\n"
            f"*Created at:* {get_date_from_ts(group_info.GroupCreated)}\n"
            f"*Group Id:* {event.chat.id}\n\n"
            f"*Admins:*\n"
            f"{tags}"
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def hello(event, args, client):
    """
    Reply with "Hi!".

    Arguments: None
    """
    try:
        await event.reply("Hi!")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def up(event, args, client):
    """
    Check if the bot is alive; replies with two response times in ms.

    Arguments: None
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    ist = dt.now()
    msg = await event.reply("…")
    st = dt.now()
    ims = (st - ist).microseconds / 1000
    msg1 = "*Pong! ——* _{}ms_"
    st = dt.now()
    await msg.edit(msg1.format(ims))
    ed = dt.now()
    ms = (ed - st).microseconds / 1000
    await msg.edit(f"1. {msg1.format(ims)}\n2. {msg1.format(ms)}")
