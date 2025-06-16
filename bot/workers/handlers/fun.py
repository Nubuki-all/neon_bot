import random

from bot.config import bot, conf
from bot.utils.bot_utils import get_json, png_to_jpg
from bot.utils.log_utils import logger
from bot.utils.msg_utils import (
    chat_is_allowed,
    clean_reply,
    construct_msg_and_evt,
    user_is_allowed,
    user_is_privileged,
)

from .yt import youtube_reply

meme_list = []


async def fun(event, args, client):
    """Help Function for the fun module"""
    try:
        pre = conf.CMD_PREFIX
        s = "\n"
        msg = (
            f"{pre}cat - *Get a random cat gif/pic*{s}"
            f"{pre}coub - *Fetches a random short video*{s}"
            f"{pre}dog - *Get a random dog pic/video*{s}"
            f"{pre}gif - *Get a random GIF from search results*{s}"
            f"{pre}gsticker - *Get a random sticker from search results*{s}"
            f"{pre}meme - *Get a random meme*"
        )
        await event.reply(msg)
    except Exception:
        await logger(Exception)
        await event.react("❌")


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
        caption = f"{nsfw_text if nsfw else ''}*{title.strip()}*\n{pl}\n\nBy u/{author} in r/{sb}"
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
        async with event.react("🌐"):
            if args:
                link += f"/{args}" if not args.isdigit() else ""
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
            if url.endswith(".png"):
                url = await png_to_jpg(url)
            await event.reply_photo(
                caption=caption,
                photo=url,
                viewonce=nsfw,
            )
    except Exception as e:
        await logger(Exception)
        return await event.reply(f"*Error:*\n{e}")


async def cat(event, args, client):
    "Fetches a random cat gif/pic."
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        async with event.react(random.choice("🐈‍⬛", "🐈")):
            result = await get_json("https://api.thecatapi.com/v1/images/search")
            if not result:
                return await event.reply("*Request Failed!*")
            url = result[0]["url"]
            if url.endswith(".gif"):
                await event.reply_gif(
                    url,
                    caption="*Meow!*",
                    as_gif=True,
                )
            else:
                await event.reply_photo(url, caption="*Meow!*")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def coub(event, args, client):
    """
    Fetches a random short video from coub;
    Arguments:
        Topic to search for.
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        async with event.react("🎦"):
            await coub_helper(event, args, client)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def coub_helper(event, args, client)
    if not args:
        args = "Genshin impact"
    random_ = ""
    page = 0
    while True:
        if page:
            random_ = f"&page={page}"
        result = await get_json(
            f"https://coub.com/api/v2/search/coubs?q={args}{random_}"
        )
        if not result:
            return await event.reply("*Request Failed!*")
        if page:
            break
        total_pages = result["total_pages"]
        page = random.choice(range(1, total_pages))

    try:
        content = random.choice(result["coubs"])
        dl_link = None
        external_dl = content["external_download"]
        permalink = content["permalink"]
        if external_dl:
            dl_link = external_dl["url"]
        title = content["title"]
    except IndexError:
        await event.reply("Couldn't fetch video…")
    else:
        ytdl = bot.group_dict.get(event.chat.id, {}).get("ytdl")
        dl_msg = "\n\n*Attempting to upload…*" if ytdl and dl_link else ""
        text = (
            f"*Title:* {title}\n*Link:* https://coub.com/view/{permalink}{dl_msg}"
        )
        rep = await event.reply(text)
        if dl_msg:
            event_ = construct_msg_and_evt(
                event.chat.id, bot.me.JID.User, rep.id, text, event.chat.server
            )
            await youtube_reply(event_, dl_link, client)


async def dog(event, args, client):
    """Fetches a random dog pic/video"""
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        async with event.react("🐾"):
            result = await get_json("https://random.dog/woof.json")
            if not result:
                return await event.reply("*Request Failed!*")
            url = result["url"]
            await logger(e=url)
            if url.casefold().endswith(".mp4"):
                return await event.reply_video(
                    url,
                    caption="*Woof!*",
                )
            await event.reply_photo(url, caption="*Woof!*")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def gif(event, args, client):
    """
    Fetches a random gif that matches the search result
    Argument:
        search_term: what to search for.
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        async with event.react("🔎"):
            await gif_helper(event, args, client)
    except Exception:
        await logger(Exception)
        await event.react("❌")

async def gif_helper(event, args, client):
    """Prevents indentation hell"""
    if not conf.TENOR_API_KEY:
        return await event.reply(
            "TENOR_API_KEY is needed for this function to work."
        )
    if not args:
        args = "genshin"
    url = f"https://tenor.googleapis.com/v2/search?key={conf.TENOR_API_KEY}&q={args}&limit=50&client_key=qiqi"
    result = await get_json(url)
    if not result:
        return await event.reply("*Request Failed!*")
    if not result["results"]:
        await event.reply("*No results!*")
        return

    gif_link = random.choice(result["results"])["media_formats"]["gif"]["url"]
    await clean_reply(event, event.reply_to_message, "reply_gif", gif_link)
    


async def sticker(event, args, client):
    """
    Fetches a random sticker that matches the search result
    Argument:
        search_term: what to search for.
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        async with event.react("🔍"):
            await sticker_helper(event, args, client)
    except Exception:
        await logger(Exception)
        await event.react("❌")

async def sticker_helper(event, args, client):
    """Prevents indentation hell"""
    if not conf.TENOR_API_KEY:
        return await event.reply(
            "TENOR_API_KEY is needed for this function to work."
        )
    if not args:
        args = "genshin"
    url = f"https://tenor.googleapis.com/v2/search?key={conf.TENOR_API_KEY}&q={args}&limit=50&client_key=qiqinator&searchfilter=sticker"
    result = await get_json(url)
    if not result:
        return await event.reply("*Request Failed!*")
    if not result["results"]:
        await event.reply("*No results!*")
        return

    sticker = random.choice(result["results"])
    duration = sticker["media_formats"]["gif"]["duration"]
    animated = True if duration else False
    link = (
        sticker["media_formats"].get("gif_transparent")
        or sticker["media_formats"]["gif"]
    )
    link = link["url"]
    # link = sticker["media_formats"]["mp4"]["url"]

    me = await bot.client.get_me()
    await clean_reply(
        event,
        event.reply_to_message,
        "reply_sticker",
        link,
        name=args,
        packname=me.PushName,
        enforce_not_broken=True,
        animated_gif=animated,
    )
    


bot.add_handler(fun, "fun")
bot.add_handler(cat, "cat")
bot.add_handler(coub, "coub")
bot.add_handler(dog, "dog")
bot.add_handler(gif, "gif")
bot.add_handler(sticker, "gsticker")
# bot.add_handler(meme, "meme")
