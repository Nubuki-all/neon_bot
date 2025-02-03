from bot.utils.ani_utils import airing_anim, anime_arch
from bot.utils.log_utils import logger
from bot.utils.msg_utils import get_args, user_is_allowed


async def airing(event, args, client):
    """
    Get airing schedule for anime.
    To use simply pass the anime title as argument
    """
    if not user_is_allowed(event.from_user.id):
        return await event.react("⛔")
    try:
        img, out = await airing_anim(args)
        await event.reply_photo(img, out)
    except Exception as e:
        await logger(Exception)
        await event.react("❌")
        await event.reply(f"Error:\n> {e}")


async def anime(event, args, client):
    """
    Fetch anime info from Anilist

    Arguments:
        anime_title - Title of anime
                or:
        anime_id (-m) Add the -m flag if you're searching with a mal_id
    """
    if not user_is_allowed(event.from_user.id):
        return await event.react("⛔")
    try:
        arg, args = get_args(
            ["-m", "store_true"],
            to_parse=args,
            get_unknown=True,
        )
        img, out = await anime_arch(args, arg)
        await event.reply_photo(img, out)
    except Exception as e:
        await logger(Exception)
        await event.react("❌")
        await event.reply(f"Error:\n> {e}")
