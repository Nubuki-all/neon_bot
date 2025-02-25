import argparse
import asyncio
import copy
import inspect
import os
import re
from functools import partial

import httpx
from bs4 import BeautifulSoup
from neonize.types import MessageWithContextInfo
from neonize.utils.enum import ChatPresence, ChatPresenceMedia, MediaType, Presence
from neonize.utils.message import extract_text, get_poll_update_message

from bot import (
    Message,
    MessageEv,
    NewAClient,
    base_msg,
    base_msg_info,
    base_msg_source,
    jid,
)
from bot.config import bot, conf
from bot.others.exceptions import ArgumentParserError

from .bot_utils import post_to_tgph
from .log_utils import logger
from .sudo_button_utils import poll_as_button_handler


class Event:
    def __init__(self):
        self.client = bot.client
        self.constructed = False

    def __str__(self):
        return self.text

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "client":
                v = None
            setattr(result, k, copy.deepcopy(v, memo))
        return result

    class User:
        def __init__(self):
            self.name = None

        def construct(self, message: MessageEv):
            self.jid = message.Info.MessageSource.Sender
            self.id = self.jid.User
            self.is_empty = message.Info.MessageSource.Sender.IsEmpty
            self.name = message.Info.Pushname
            self.server = self.jid.Server

    class Chat:
        def __init__(self):
            self.name = None

        def construct(self, message: MessageEv):
            self.jid = message.Info.MessageSource.Chat
            self.id = self.jid.User
            self.is_empty = message.Info.MessageSource.Chat.IsEmpty
            self.is_group = message.Info.MessageSource.IsGroup
            self.server = self.jid.Server

    def _construct_media(self):
        for msg, v in self._message.ListFields():
            if not msg.name.endswith("Message"):
                continue
            setattr(self, msg.name.split("M")[0], v)
            if not hasattr(v, "contextInfo"):
                continue
            self.media = v
            break

    def construct(self, message: MessageEv, add_replied: bool = True):
        self.chat = self.Chat()
        self.chat.construct(message)
        self.from_user = self.User()
        self.from_user.construct(message)
        self.message = message

        # To do support other message types
        self.id = message.Info.ID
        self.type = message.Info.Type
        self.type = "text" if message.Info.MediaType == "url" else self.type
        self.media_type = message.Info.MediaType
        self._message = message.Message
        self.ext_msg = message.Message.extendedTextMessage
        self.text_msg = message.Message.conversation
        self.short_text = self.text_msg
        self.text = self.ext_msg.text
        # mention_str = f"@{(self.w_id.split('@'))[0]}"
        # self.mentioned = self.text.startswith(mention_str) if self.text else False
        # if self.mentioned:
        #    self.text = (self.text.split(maxsplit=1)[1]).strip()
        self.text = self.text or self.short_text or None
        # To do expand quoted; has members [stanzaID, participant,
        # quotedMessage.conversation]
        self.audio = None
        self.document = None
        self.image = None
        self.media = None
        self.reaction = None
        self.video = None
        self._construct_media()
        self.caption = (extract_text(self._message) or None) if not self.text else None

        self.quoted = (
            self.media.contextInfo
            if add_replied and self.media and self.media.contextInfo.ByteSize()
            else None
        )
        self.quoted_audio = self.quoted_document = self.quoted_image = (
            self.quoted_video
        ) = self.quoted_viewonce = None
        if self.quoted:
            if self.quoted.quotedMessage.audioMessage.ByteSize():
                self.quoted_audio = self.quoted.quotedMessage.audioMessage

            elif (
                self.quoted.quotedMessage.documentWithCaptionMessage.message.documentMessage.ByteSize()
            ):
                self.quoted_document = (
                    self.quoted.quotedMessage.documentWithCaptionMessage.message.documentMessage
                )
            elif self.quoted.quotedMessage.documentMessage.ByteSize():
                self.quoted_document = self.quoted.quotedMessage.documentMessage
            elif self.quoted.quotedMessage.imageMessage.ByteSize():
                self.quoted_image = self.quoted.quotedMessage.imageMessage
            elif self.quoted.quotedMessage.videoMessage.ByteSize():
                self.quoted_video = self.quoted.quotedMessage.videoMessage
            elif self.quoted.quotedMessage.viewOnceMessageV2.message.ByteSize():
                self.quoted_viewonce_ = (
                    self.quoted.quotedMessage.viewOnceMessageV2.message
                )
                for x in ("imageMessage", "videoMessage"):
                    self.quoted_viewonce = getattr(self.quoted_viewonce_, x)
                    if self.quoted_viewonce.ByteSize():
                        break
            elif (
                self.quoted.quotedMessage.viewOnceMessageV2Extension.message.ByteSize()
            ):
                self.quoted_viewonce = (
                    self.quoted.quotedMessage.viewOnceMessageV2Extension.message.audioMessage
                )

        self.quoted_text = (
            (
                self.quoted.quotedMessage.conversation
                or self.quoted.quotedMessage.extendedTextMessage.text
            )
            if self.quoted
            else None
        )
        self.quoted_msg = (
            self.quoted_text
            or self.quoted_audio
            or self.quoted_document
            or self.quoted_image
            or self.quoted_video
            or self.quoted_viewonce
        )
        self.reply_to_message = self.get_quoted_msg()
        self.outgoing = message.Info.MessageSource.IsFromMe
        self.is_status = message.Info.MessageSource.Chat.User.casefold() == "status"
        self.constructed = True
        return self

    async def _send_message(self, chat, message, link_preview=True):
        await self.send_typing_status()
        response = await self.client.send_message(
            to=chat, message=message, link_preview=link_preview
        )
        await self.send_typing_status(False)
        msg = self.gen_new_msg(response.ID)
        return construct_event(msg)

    async def delete(self):
        await self.client.revoke_message(self.chat.jid, self.from_user.jid, self.id)
        return

    async def edit(self, text: str):
        msg = Message(conversation=text)
        response = await self.client.edit_message(self.chat.jid, self.id, msg)
        msg = self.gen_new_msg(response.ID)
        return construct_event(msg)

    async def react(self, emoji: str):
        reaction = await self.client.build_reaction(
            self.chat.jid, self.from_user.jid, self.id, emoji
        )
        return await self.client.send_message(self.chat.jid, reaction)

    async def reply(
        self,
        text: str = None,
        file: str | bytes = None,
        file_name: str = None,
        image: str = None,
        quote: bool = True,
        link_preview: bool = True,
        reply_privately: bool = False,
        message: MessageWithContextInfo = None,
    ):
        if not self.constructed:
            return
        if file:
            return await self.reply_document(file, file_name, text, quote)
        if image and file_name:
            return await self.reply_photo(image, text, quote)
        text = text or message
        if not text:
            raise Exception("Specify a text to reply with.")
        # msg_id = self.id if quote else None
        if not quote:
            return await self._send_message(self.chat.jid, text, link_preview)
        await self.send_typing_status()

        try:
            response = await self.client.reply_message(
                text,
                self.message,
                link_preview=link_preview,
                reply_privately=reply_privately,
            )
        except httpx.HTTPStatusError:
            await logger(Exception)
            response = await self.client.reply_message(
                text,
                self.message,
                link_preview=False,
                reply_privately=reply_privately,
            )
        # self.id = response.ID
        # self.text = text
        # new_jid = jid.build_jid(conf.PHNUMBER)
        # self.user.jid = new_jid
        # self.user.id = new_jid.User

        # self.user.name = None
        await self.send_typing_status(False)
        msg = self.gen_new_msg(response.ID, private=reply_privately)
        return construct_event(msg)

    async def reply_audio(
        self,
        audio: str | bytes,
        ptt: bool = False,
        quote: bool = True,
    ):
        quoted = self.message if quote else None

        response = await self.client.send_audio(
            self.chat.jid, audio, ptt, quoted=quoted
        )
        msg = self.gen_new_msg(response.ID)
        return construct_event(msg)

    async def reply_document(
        self,
        document: str | bytes,
        file_name: str = None,
        caption: str = None,
        quote: bool = True,
    ):
        quoted = self.message if quote else None
        _, file_name = (
            os.path.split(document)
            if not file_name and isinstance(document, str)
            else (None, file_name)
        )
        response = await self.client.send_document(
            self.chat.jid, document, caption, filename=file_name, quoted=quoted
        )
        msg = self.gen_new_msg(response.ID)
        return construct_event(msg)

    async def reply_gif(
        self,
        gif: str | bytes,
        caption: str = None,
        quote: bool = True,
        viewonce: bool = False,
        as_gif: bool = True,
    ):
        quoted = self.message if quote else None
        response = await self.client.send_video(
            self.chat.jid,
            gif,
            caption,
            quoted=quoted,
            viewonce=viewonce,
            gifplayback=as_gif,
            is_gif=True,
        )
        msg = self.gen_new_msg(response.ID)
        return construct_event(msg)

    async def reply_photo(
        self,
        photo: str | bytes,
        caption: str = None,
        quote: bool = True,
        viewonce: bool = False,
    ):
        quoted = self.message if quote else None
        response = await self.client.send_image(
            self.chat.jid, photo, caption, quoted=quoted, viewonce=viewonce
        )
        msg = self.gen_new_msg(response.ID)
        return construct_event(msg)

    async def reply_sticker(
        self,
        file: str | bytes,
        quote: bool = True,
        name: str = "",
        packname: str = "",
        crop: bool = False,
        enforce_not_broken: bool = False,
    ):
        quoted = self.message if quote else None
        response = await self.client.send_sticker(
            self.chat.jid,
            file,
            quoted=quoted,
            name=name,
            packname=packname,
            crop=crop,
            enforce_not_broken=enforce_not_broken,
        )
        msg = self.gen_new_msg(response.ID)
        return construct_event(msg)

    async def reply_video(
        self,
        video: str | bytes,
        caption: str = None,
        quote: bool = True,
        viewonce: bool = False,
        as_gif: bool = False,
    ):
        quoted = self.message if quote else None
        response = await self.client.send_video(
            self.chat.jid,
            video,
            caption,
            quoted=quoted,
            viewonce=viewonce,
            gifplayback=as_gif,
        )
        msg = self.gen_new_msg(response.ID)
        return construct_event(msg)

    async def send_typing_status(self, typing=True):
        status = (
            ChatPresence.CHAT_PRESENCE_COMPOSING
            if typing
            else ChatPresence.CHAT_PRESENCE_PAUSED
        )
        return await self.client.send_chat_presence(
            self.chat.jid, status, ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT
        )

    async def upload_file(self, file: bytes):
        response = await self.client.upload(file)
        # msg = self.gen_new_msg(response.ID)
        # return construct_event(msg)
        return response

    def gen_new_msg(
        self, msg_id: str, user_id: str = None, chat_id: str = None, private=False
    ):
        msg = copy.deepcopy(self.message)
        msg.Info.ID = msg_id
        if private:
            msg.Info.MessageSource.Chat.User = self.from_user.id
            msg.Info.MessageSource.Chat.Server = self.from_user.server
        msg.Info.MessageSource.Sender.User = user_id or conf.PH_NUMBER
        return msg

    def get_quoted_msg(self):
        if not (self.quoted and self.quoted.stanzaID):
            return
        # msg = self.gen_new_msg(
        # self.quoted.stanzaID, (self.quoted.participant.split("@"))[0], self.chat.id, self.text, self.chat.jid.Server
        # )
        if self.quoted.remoteJID:
            chat_id, server = self.quoted.remoteJID.split("@", maxsplit=1)
        else:
            chat_id = self.chat.id
            server = self.chat.server
        msg = construct_message(
            chat_id,
            (self.quoted.participant.split("@"))[0],
            self.quoted.stanzaID,
            None,
            server,
            self.quoted.quotedMessage,
        )
        return construct_event(msg, False)


async def download_replied_media(event) -> bytes:
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


def tag_admins(members: list):
    tags = str()
    for member in members:
        if member.IsAdmin:
            tags += f"@{member.JID.User} "
    return tags.rstrip()


def tag_users(members: list):
    tags = str()
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


function_dict = {None: []}


def register(key: str | None = None):
    def dec(fn):
        nonlocal key
        if not key:
            function_dict[key].append(fn)
        else:
            key = conf.CMD_PREFIX + key
            function_dict.update({key: fn})

    return dec


bot.register = register


async def handler_helper(funcs):
    await asyncio.sleep(0.1)
    await asyncio.gather(*funcs)


async def on_message(client: NewAClient, message: MessageEv):
    try:
        # await logger(e=message)
        event = construct_event(message)
        bot.pending_saved_messages.append(event)
        if get_poll_update_message(event.message):
            return await poll_as_button_handler(event)
        if event.type == "text" and event.text:
            command, args = (
                event.text.split(maxsplit=1)
                if len(event.text.split()) > 1
                else (event.text, None)
            )
            func = function_dict.get(command)
            if func:
                # await func(client, event)
                future = asyncio.run_coroutine_threadsafe(func(client, event), bot.loop)
                future.result()
        func_list = []
        for func in function_dict[None]:
            func_list.append(func(client, event))
        future = asyncio.run_coroutine_threadsafe(handler_helper(func_list), bot.loop)
        future.result()
    except Exception:
        await logger(e="Unhandled Exception:")
        await logger(Exception)


def construct_event(message: MessageEv, add_replied=True):
    msg = Event()
    return msg.construct(message, add_replied=add_replied)


def construct_message(
    chat_id, user_id, msg_id, text, server="s.whatsapp.net", Msg=None
):
    if text:
        message = Message(conversation=text)
    else:
        message = Msg

    return base_msg(
        Message=message,
        Info=base_msg_info(
            ID=msg_id,
            MessageSource=base_msg_source(
                Chat=jid.build_jid(chat_id, server),
                Sender=jid.build_jid(user_id),
            ),
        ),
    )


def construct_msg_and_evt(*args, **kwargs):
    return construct_event(construct_message(*args, **kwargs))


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
        tgh_link = str()
        title = data.get("title")
        url = data.get("link")
        # auth_text = f" by {author}" if author else str()
        caption = f"*{title}*"
        caption += f"\n> {summary}" if summary else str()
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


async def event_handler(
    event,
    function,
    client=None,
    require_args=False,
    disable_help=False,
    split_args=" ",
    default_args: str = False,
    use_default_args=False,
):
    args = (
        event.text.split(split_args, maxsplit=1)[1].strip()
        if len(event.text.split()) > 1
        else None
    )
    args = default_args if use_default_args and default_args is not False else args
    help_tuple = ("--help", "-h")
    if (
        (require_args and not args)
        or (args and args.casefold() in help_tuple)
        or (require_args and not (default_args or default_args is False))
        or (default_args in help_tuple)
    ):
        if disable_help:
            return
        return await event.reply(f"{inspect.getdoc(function)}")
    await function(event, args, client)
