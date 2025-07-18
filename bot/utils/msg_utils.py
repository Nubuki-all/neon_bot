import argparse
import asyncio
import re
from functools import partial

from bs4 import BeautifulSoup
from neonize.utils.enum import Presence

from bot import jid
from bot.config import bot, conf
from bot.others.exceptions import ArgumentParserError

from .bot_utils import post_to_tgph

# isort: off
from .events import (
    Event,  # noqa  # pylint: disable=unused-import
    construct_event,
    construct_message,
    construct_msg_and_evt,
    download_media,
    event_handler,
    function_dict,
    patch_msg_sender,
)

# isort: on

from .log_utils import logger


def chat_is_allowed(event: Event):
    if conf.ALLOWED_CHATS:
        return event.chat.id in conf.ALLOWED_CHATS
    if not event.chat.is_group:
        return not bot.ignore_pm
    else:
        return not bot.group_dict.get(event.chat.id, {}).get("disabled", False)


def find_role_mentions(text, roles):
    """
    Finds specified role mentions in text and checks if they're plural (end with 's')
    Args:
        text: Input string to search
        roles: List of role base names (e.g., ['mod', 'admin', 'all', 'everyone'])
    Returns:
        List of tuples: (matched_role, is_plural)
    """
    if not roles:
        return []
    role_map = {role.lower(): role for role in roles}
    sorted_roles = sorted(roles, key=len, reverse=True)
    pattern = (
        r"(?<!\w)@("
        + "|".join(re.escape(role) for role in sorted_roles)
        + r")(s)?(?!\w)"
    )
    regex = re.compile(pattern, re.IGNORECASE)
    results = []
    for match in regex.finditer(text):
        base_role = match.group(1)  # The base role without @ or s
        plural_suffix = match.group(2)  # 's' if present, None otherwise
        role_key = base_role.lower()
        if role_key in role_map:
            original_role = role_map[role_key]
            is_plural = plural_suffix is not None
            results.append((original_role, is_plural))
    return results


def get_afk_status(user: str):
    return bot.user_dict.get(user, {}).get("afk", False)


def get_mentioned(text: str):
    return [jid.group(1) for jid in re.finditer(r"@([0-9]{5,16}|0)", text)]


def tag_all_users_in_role(members: list):
    tags = ""
    for member in members:
        tags += f"@{member} "
    return tags.rstrip()


def tag_admins(members: list):
    tags = ""
    for member in members:
        if member.IsAdmin:
            tags += f"@{member.JID.User} "
    return tags.rstrip()


def tag_owners():
    tags = ""
    for user in conf.OWNER.split():
        tags += f"@{user} "
    return tags.rstrip()


def tag_sudoers():
    tags = ""
    for user in bot.user_dict.keys():
        if not bot.user_dict.get(user, {}).get("sudoer", False):
            continue
        tags += f"@{user} "
    return tags.rstrip()


def tag_users(members: list):
    tags = ""
    for member in members:
        tags += f"@{member.JID.User} "
    return tags.rstrip()


def user_is_admin(user: str, members: list):
    for member in members:
        if user == member.JID.User or user == member.PhoneNumber.User:
            return member.IsAdmin


def user_is_afk(user: str):
    return bool(get_afk_status(user))


def user_is_allowed(user: str | int):
    user = str(user)
    return not (
        bot.user_dict.get(user, {}).get("banned", False)
        or bot.user_dict.get(user, {}).get("fbanned", False)
        or user in conf.BANNED_USERS
    )


def user_is_banned_by_ownr(user: str | int):
    user = str(user)
    return (
        bot.user_dict.get(user, {}).get("fbanned", False) or user in conf.BANNED_USERS
    )


def user_is_dev(user: str):
    user = int(user)
    return user == conf.DEV


def user_is_owner(user: str | int):
    user = str(user)
    return user in conf.OWNER


def user_is_privileged(user):
    return user_is_owner(user) or user_is_sudoer(user)


def user_is_sudoer(user: str | int):
    user = str(user)
    return bot.user_dict.get(user, {}).get("sudoer", False)


async def get_user_info(user_id: str, server: str = "s.whatsapp.net"):
    jid_ = jid.build_jid(user_id, server)
    info = await bot.client.contact.get_contact(jid_)
    if not info.Found:
        try:
            jid_ = (
                await bot.client.get_pn_from_lid(jid_)
                if jid_.Server == "lid"
                else await bot.client.get_lid_from_pn(jid_)
            )
            info = await bot.client.contact.get_contact(jid_)
        except Exception:
            pass
    return info


async def send_presence(online=True):
    presence = Presence.AVAILABLE if online else Presence.UNAVAILABLE
    return await bot.client.send_presence(presence)


def sanitize_text(text: str, truncate=True) -> str:
    if not text:
        return text
    text = BeautifulSoup(text, "html.parser").text
    return (text[:900] + "…") if len(text) > 900 and truncate else text


async def parse_and_send_rss(data: dict, chat_ids: list = None):
    try:
        author = data.get("author")
        chats = chat_ids or conf.RSS_CHAT.split()
        pics = data.get("pic")
        content = data.get("content")
        summary = sanitize_text(data.get("summary"))
        tgh_link = ""
        title = data.get("title")
        url = data.get("link")
        # auth_text = f" by {author}" if author else str()
        caption = f"*{title}*"
        caption += f"\n> {summary}" if summary else ""
        if content:
            if len(content) > 65536:
                content = (
                    content[:65430]
                    + "<strong>...<strong><br><br><strong>(TRUNCATED DUE TO CONTENT EXCEEDING MAX LENGTH)<strong>"
                )
            tgh_link = (await post_to_tgph(title, content, author, url))["url"]
            caption += f"\n\n*Telegraph:* {tgh_link}\n*Feed Link:* {url}"
        expanded_chat = []
        for chat in chats:
            (
                expanded_chat.append(chat)
                if chat
                else expanded_chat.extend(conf.RSS_CHAT.split())
            )
        func_list = []
        for chat in expanded_chat:
            top_chat = chat.split(":")
            chat, server = (
                map(str, top_chat)
                if len(top_chat) > 1
                else (str(top_chat[0]), "s.whatsapp.net")
            )
            func = send_rss(caption, chat, pics, server)
            func_list.append(func)
        await asyncio.gather(*func_list)
    except Exception:
        await logger(Exception)


async def send_rss(caption, chat, pics, server):
    try:
        len_pic = len(pics)
        if len_pic > 1:
            i = 0

            send_media = bot.client.send_image
            if pics[0].endswith(".jpg"):
                pass
            elif pics[0].endswith(".gif"):
                send_media = bot.client.send_video

            rep = await send_media(
                jid.build_jid(chat, server=server),
                pics[0],
                caption,
            )
            message = construct_message(
                chat, bot.client.me.JID.User, rep.ID, "image", server=server
            )
            msg = construct_event(message)
            for img in pics[1:]:
                i += 1

                reply_media = msg.reply_photo
                if img.endswith(".jpg"):
                    pass
                elif img.endswith(".gif"):
                    reply_media = msg.reply_gif

                caption = f"*({i} of {len_pic - 1})*"
                msg = await reply_media(img, caption, quote=True)
        elif pics:

            send_media = bot.client.send_image
            if pics[0].endswith(".jpg"):
                pass
            elif pics[0].endswith(".gif"):
                send_media = bot.client.send_video

            await send_media(
                jid.build_jid(chat, server),
                pics[0],
                caption,
            )
        else:
            await bot.client.send_message(
                jid.build_jid(chat, server),
                caption,
                link_preview=True,
            )
    except Exception:
        await logger(Exception)


async def clean_reply(event, reply, func, *args, **kwargs):
    clas = reply if reply else event
    func = getattr(clas, func)
    pfunc = partial(func, *args, **kwargs)
    return await pfunc()


class ThrowingArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentParserError(message)


def line_split(line):
    return [t.strip("\"'") for t in re.findall(r'[^\s"]+|"[^"]*"', line)]


def get_args(*args, to_parse: str, get_unknown=False):
    parser = ThrowingArgumentParser(
        description="parse command flags", exit_on_error=False, add_help=False
    )
    for arg in args:
        if isinstance(arg, list):
            parser.add_argument(arg[0], action=arg[1], required=False)
        else:
            parser.add_argument(arg, type=str, required=False)
    flag, unknowns = parser.parse_known_args(line_split(to_parse))
    if get_unknown:
        unknown = " ".join(map(str, unknowns))
        return flag, unknown
    return flag


def extract_bracketed_prefix(s: str) -> str | None:
    """
    Match string starting with [text] and capture the text
    """
    match = re.match(r"^\[(.*?)\]", s)
    return match.group(1) if match else None
