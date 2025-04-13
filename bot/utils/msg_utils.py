import argparse
import asyncio
import inspect
import re
from functools import partial

from bs4 import BeautifulSoup
from neonize.utils.enum import MediaType, Presence

from bot import jid
from bot.config import bot, conf
from bot.others.exceptions import ArgumentParserError

from .bot_utils import post_to_tgph
from .events import Event  # noqa  # isort: skip  # pylint: disable=unused-import
from .events import (
    construct_event,
    construct_message,
    construct_msg_and_evt,
    event_handler,
)
from .log_utils import logger


async def download_replied_media(event: Event) -> bytes:
    if item := event.quoted_image:
        mtype = "image"
        media_type = MediaType.MediaImage
    elif item := event.quoted_video:
        mtype = "video"
        media_type = MediaType.MediaVideo
    elif item := event.quoted_audio:
        mtype = "audio"
        media_type = MediaType.MediaAudio
    elif item := event.quoted_document:
        mtype = "document"
        media_type = MediaType.MediaDocument
    elif item := event.reply_to_message.sticker:
        mtype = "image"
        media_type = MediaType.MediaImage
    else:
        raise Exception(
            inspect.cleandoc(
                f"""Expected either:
                ImageMessage
                VideoMessage
                AudioMessage
                DocumentMessage
                not {type(event.quoted_msg).__name__}
                """
            )
        )

    direct_path = item.directPath
    enc_file_hash = item.fileEncSHA256
    file_hash = item.fileSHA256
    media_key = item.mediaKey
    file_length = item.fileLength
    mms_type = mtype
    return await bot.client.download_media_with_path(
        direct_path,
        enc_file_hash,
        file_hash,
        media_key,
        file_length,
        media_type,
        mms_type,
    )


def chat_is_allowed(event: Event):
    if conf.ALLOWED_CHATS:
        return event.chat.id in conf.ALLOWED_CHATS
    if not event.chat.is_group:
        return not bot.ignore_pm
    else:
        return not bot.group_dict.get(event.chat.id, {}).get("disabled", False)


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
        if user == member.JID.User:
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


async def get_user_info(user_id):
    return await bot.client.contact.get_contact(jid.build_jid(user_id))


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
                chat, conf.PH_NUMBER, rep.ID, "image", server=server
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
