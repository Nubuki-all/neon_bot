import anilist

from bot.config import bot
from bot.utils.ani_utils import airing_anim, anime_arch
from bot.utils.log_utils import logger
from bot.utils.msg_utils import construct_msg_and_evt, get_args, user_is_allowed
from bot.utils.sudo_button_utils import create_sudo_button, wait_for_button_response



ani_client = anilist.AsyncClient()

async def airing(event, args, client):
    """
    Get airing schedule for anime.
    To use simply pass the anime title as argument
    """
    if not user_is_allowed(event.from_user.id):
        return await event.react("⛔")
    try:
        if not args.isdigit():
            args = await anime_search(event, args, client)
            if args == "":
                return await event.reply("Yh, i give up!")
            if not args:
                return await event.reply("*Couldn't find any anime with that name.*")
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
        if not args.isdigit() and not arg.m:
            args = await anime_search(event, args, client)
            if args == "":
                return await event.reply("Yh, i give up!")
            if not args:
                return await event.reply("*Couldn't find any anime with that name.*")
        img, out = await anime_arch(args, arg)
        await event.reply_photo(img, out)
    except Exception as e:
        await logger(Exception)
        await event.react("❌")
        await event.reply(f"Error:\n> {e}")


async def anime_search(event, args, client):

    #query = args.replace(" ", "%20")
    search_result, pages = await ani_client.search_anime(args, limit=11)

    if not search_result:
        return None

    button_dict = []
    for i, anime in enumerate(search_result, start=1):
        title = 
        text = anime.title.english or anime.title.romaji or anime.title.native
        button_dict.append(
            {
                anime.id: [f"{i}. {text}", text]
            }
        )
    title = f"{event.from_user.name} please select the anime you want to fetch info for."
    poll_msg_, msg_id = await create_sudo_button(
        title, button_dict, event.chat.jid, user, 1, cfm_btn_txt, event.message
    )
    poll_msg = construct_msg_and_evt(
        event.chat.id, bot.me.JID.User, msg_id, None, event.chat.server, poll_msg_
    )
    results = await wait_for_button_response(msg_id)
    await poll_msg.delete()
    if not results:
        await event.reply("Time out!")
        return ""
    return f"{results[0]}"

