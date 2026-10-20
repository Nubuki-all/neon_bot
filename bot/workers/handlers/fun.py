import random
from urllib.parse import quote_plus

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

from .media_dl import youtube_reply

meme_list = []


async def fun(event, args, client):
    """
    Shows the list of fun commands.

    Arguments: None
    """
    try:
        pre = conf.CMD_PREFIX
        s = "\n"
        msg = (
            f"{pre}cat - *Get a random cat pic/gif*{s}"
            f"{pre}coub [topic] - *Get a random coub video link (default: Anime)*{s}"
            f"{pre}dog - *Get a random dog pic/video*{s}"
            f"{pre}gif [search] - *Get a random GIF matching search (default: anime)*{s}"
            f"{pre}gsticker [search] - *Get a random sticker matching search (default: anime)*{s}"
            f"{pre}meme [subreddit] - *Get a random reddit meme*"
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
        caption = f"{
            nsfw_text if nsfw else ''}*{
            title.strip()}*\n{pl}\n\nBy u/{author} in r/{sb}"
        url = result.get("url")
        filename = f"{_id}.{url.split('.')[-1]}"
        nsfw = False if pm else nsfw
        break
    return caption, url, filename, nsfw


async def getmeme(event, args, client):
    """
    Fetches a random reddit meme via meme-api.com and sends it as a photo or gif.
    NSFW memes are blocked in groups when NSFW blocking is on; otherwise in groups they are sent as view-once.

    Arguments:
        subreddit: [Optional] subreddit to fetch from (default: random; numeric input is ignored)
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
            caption, url, filename, nsfw = await gen_meme(
                link, not (event.chat.is_group)
            )
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
    """
    Fetches a random cat pic or gif from thecatapi.com.

    Arguments: None
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        async with event.react(random.choice(("🐈‍⬛", "🐈"))):
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
    Searches coub for a topic and replies with the title and link of a random result.
    If the group has ytdl enabled and the coub has a download link, the video is also uploaded.

    Arguments:
        topic: [Optional] what to search for (default: Anime)
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


async def coub_helper(event, args, client):
    if not args:
        args = "Anime"
    random_ = ""
    page = 0
    while True:
        if page:
            random_ = f"&page={page}"
        result = await get_json(
            f"https://coub.com/api/v2/search/coubs?q={quote_plus(args)}{random_}"
        )
        if not result:
            return await event.reply("*Request Failed!*")
        if page:
            break
        total_pages = max(result["total_pages"] or 1, 1)
        page = random.randint(1, total_pages)

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
        text = f"*Title:* {title}\n*Link:* https://coub.com/view/{permalink}{dl_msg}"
        rep = await event.reply(text)
        if dl_msg:
            event_ = construct_msg_and_evt(
                event.chat.id, bot.client.me.JID.User, rep.id, text, event.chat.server
            )
            await youtube_reply(event_, dl_link, client)


async def dog(event, args, client):
    """
    Fetches a random dog pic or video from random.dog.

    Arguments: None
    """
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
    Sends a random GIF from Klipy matching a search term; requires KLIPY_API_KEY.
    If used as a reply, the GIF is sent in reply to the replied message.

    Arguments:
        search_term: [Optional] what to search for (default: anime)
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


async def klipy_search(query, pages=2, **params):
    """
    Search Klipy's Tenor-compatible API, following `next` for up to `pages`
    pages (50 results each) so random picks have a bigger pool.
    Klipy stops at 2 pages (100 results) per query.
    Returns None if the first request fails.
    """
    url = (
        f"https://api.klipy.com/v2/search?"
        f"key={conf.KLIPY_API_KEY}"
        f"&q={quote_plus(query)}"
        f"&limit=50"
        f"&client_key=neon"
    ) + "".join(f"&{k}={v}" for k, v in params.items())
    results, seen, pos = [], set(), None
    for _ in range(pages):
        result = await get_json(f"{url}&pos={quote_plus(pos)}" if pos else url)
        if not result:
            return None if not results else results
        for item in result.get("results") or []:
            if item.get("id") not in seen:
                seen.add(item.get("id"))
                results.append(item)
        # an empty or "0" next means there are no more results
        if not (pos := result.get("next")) or pos == "0":
            break
    return results


async def gif_helper(event, args, client):
    """Prevents indentation hell"""
    if not conf.KLIPY_API_KEY:
        return await event.reply("KLIPY_API_KEY is needed for this function to work.")

    if not args:
        args = "anime"

    results = await klipy_search(args)

    if results is None:
        return await event.reply("*Request Failed!*")

    if not results:
        return await event.reply("*No results!*")

    gif_link = random.choice(results)["media_formats"]["gif"]["url"]

    await clean_reply(
        event,
        event.reply_to_message,
        "reply_gif",
        gif_link,
    )


async def sticker(event, args, client):
    """
    Sends a random sticker from Klipy matching a search term; requires KLIPY_API_KEY.
    If used as a reply, the sticker is sent in reply to the replied message.

    Arguments:
        search_term: [Optional] what to search for (default: anime)
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
    if not conf.KLIPY_API_KEY:
        return await event.reply("KLIPY_API_KEY is needed for this function to work.")

    if not args:
        args = "anime"

    results = await klipy_search(args, searchfilter="sticker")

    if results is None:
        return await event.reply("*Request Failed!*")

    if not results:
        return await event.reply("*No results!*")

    sticker = random.choice(results)

    duration = sticker["media_formats"]["gif"].get("duration", 0)
    animated = bool(duration)

    media = (
        sticker["media_formats"].get("gif_transparent")
        or sticker["media_formats"]["gif"]
    )

    link = media["url"]

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
