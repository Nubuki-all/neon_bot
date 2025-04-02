import random
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

from yt import youtube_reply
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
        await event.reply_photo(
            caption=caption,
            photo=url,
            viewonce=nsfw,
        )
    except Exception as e:
        await logger(Exception)
        return await event.reply(f"*Error:*\n{e}")


async def cat(event, args, client):
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        result = await get_json("https://api.thecatapi.com/v1/images/search")
    
        if not result:
            return await event.reply("*Request Failed!*")
        url = result[0]["url"]
        if url.endswith(".gif"):
            await event.reply_gif(
                    caption="*Meow!*",
                    gif=url,
                    viewonce=nsfw,
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
        if not args:
            args = "Genshin impact"
        result = await get_json(f"https://coub.com/api/v2/search/coubs?q={args}")
        if not result:
                return await event.reply("*Request Failed!*")
        try:
            content = random.choice(result["coubs"])
            permalink = content["permalink"]
            links = content["external_download"]["url"]
            title = content["title"]
        except IndexError:
            await event.reply("Couldn't fetch video…")
        else:
            await event.reply(f"*Title:* {title}\n*Link:* https://coub.com/view/{permalink}\n\n*Attempting to upload…*")
            await youtube_reply(event, links, client)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def dog(event, args, client):
    """Fetch the image of a random dog"""
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        result = await get_json("https://random.dog/woof.json")
        if not result:
                return await event.reply("*Request Failed!*")
    
        await event.reply_photo(result["url"], caption="*Woof!*")
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
        if not conf.TENOR_API_KEY:
            return await event.reply("TENOR_API_KEY is needed for this function to work.")
        if not args:
            args="genshin"
        url = f"https://tenor.googleapis.com/v2/search?key={conf.TENOR_API_KEY}&q={args}&limit=50&client_key=qiqi"
        result = await get_json(url)
        if not result:
            return await event.reply("*Request Failed!*")
        if not result["results"]:
            await event.reply("*No results!*")
            return
    
        gif_link = random.choice(rjson["results"])["media_formats"]["gif"]["url"]
        await event.reply_gif(gif_link)
    except Exception:
        await logger(Exception)
        await event.react("❌")