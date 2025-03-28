from datetime import datetime as dt

from bot.config import bot, conf
from bot.utils.bot_utils import get_date_from_ts, get_json
from bot.utils.log_utils import logger
from bot.utils.msg_utils import (
    chat_is_allowed,
    tag_admins,
    user_is_admin,
    user_is_allowed,
    user_is_privileged,
)

meme_list = []


async def gen_meme(link, pm=False):
    i = 1
    while True:
        result = await get_json(link)
        _id = result.get("ups")
        title = result.get("title")
        if not title:
            return None, None, None, None
        author = result.get("author")
        pl = result.get("postLink")
        if i > 100:
            raise Exception("Request Timeout!")
        i += 1
        if pl in meme_list:
            continue
        if len(meme_list) > 10000:
            meme_list.clear()
        nsfw = result.get("nsfw")
        if bot.block_nsfw and nsfw and not pm:
            return None, None, None, True
        meme_list.append(pl)
        sb = result.get("subreddit")
        nsfw_text = "*🔞 NSFW*\n"
        caption = f"{nsfw_text if nsfw else str()}*{title.strip()}*\n{pl}\n\nBy u/{author} in r/{sb}"
        url = result.get("url")
        filename = f"{_id}.{url.split('.')[-1]}"
        nsfw = False if pm else nsfw
        break
    return caption, url, filename, nsfw


async def getmeme(event, args, client):
    """
    Fetches a random meme from reddit
    Uses meme-api.com

    Arguments:
    subreddit - custom subreddit
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    link = "https://meme-api.com/gimme"
    try:
        if args:
            link += f"/{args}" if not args.isdigit() else str()
        caption, url, filename, nsfw = await gen_meme(link, not (event.chat.is_group))
        if not url:
            if nsfw:
                return await event.reply("*NSFW is blocked!*")
            return await event.reply("*Request Failed!*")
        if url.endswith(".gif"):
            return await event.reply_gif(
                caption=caption,
                gif=url,
                viewonce=nsfw,
                as_gif=True,
            )
        await event.reply_photo(
            caption=caption,
            photo=url,
            viewonce=nsfw,
        )
    except Exception as e:
        await logger(Exception)
        return await event.reply(f"*Error:*\n{e}")


async def getcmds(event, args, client):
    """
    Get list of commands

    Arguments:
        None
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
{pre}meme - *Get a random meme*
{pre}sanitize - *Sanitize link or message*
{pre}sticker - *Turns images to stickers*
{pre}stick2img - *Turns stickers to images/gifs*
{pre}get - *Get previously saved item*
{pre}save - *Save a replied text/media*
{pre}del_note - *Delete a saved item*
{pre}afk - *Enable AFK mode*
{pre}random - *Get a random choice*
{pre}upscale - {'*Upscale replied image*' if not bot.disable_cic else '_Currently not available!_'}
{pre}anime - *Fetch anime info from anilist*
{pre}airing - *Fetch anime airing info from anilist*
{pre}msg_ranking - *Get a group's msg ranking*
{pre}undel - *Undelete a user messages*
{pre}ping - *Check if bot is alive*
{pre}bash - *[Dev.] Run bash commands*
{pre}eval - *[Dev.] Evaluate python commands*
{pre}ban - *[Owner] prevent a user from using bot*
{pre}unban - *[Owner] unban a user*
{pre}sudo - *[Owner] Promote a user to sudoers*
{pre}rss - *[Owner | Sudo] Setup bot to auto post RSS feeds*
{pre}update - *[Owner | Sudo] Update & restarts bot*
{pre}restart - *[Owner | Sudo] Restarts bot*
{pre}ytdl_* - *[Owner | Sudo] Disables/Enables Ytdl*
{pre}amr_* - *[Owner | Sudo] Disables/Enables Auto msg ranking*
{pre}greetings - *[Owner | Sudo] Disables/Enables greetings*
{pre}roles - *Get commands for roles*
{pre}disable - *[Owner | Sudo] Disable bot in a GC*
{pre}enable - *[Owner | Sudo] Enable bot in a GC*
{pre}del - *[Owner | Sudo] Delete bot's messages*
{pre}gc_info - *[Owner | Sudo] Get group info*
{pre}pause - *[Owner] Pauses bot*

* expands to _ytdl_enable/ytdl_disable_
* expands to _amr_enable/amr_disable_"""
        await event.reply(msg)
    except Exception as e:
        await logger(Exception)
        return await event.reply(f"*Error:*\n{e}")


async def gc_info(event, args, client):
    """
    Get the group chats Owner
    Arguments: [None]
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
        tags = str()
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


async def hello(event, args, client):
    try:
        await event.reply("Hi!")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def up(event, args, client):
    """ping bot!"""
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
