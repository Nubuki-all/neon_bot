import asyncio
import copy
import inspect
import os
from collections import deque

import httpx
from neonize.types import MessageWithContextInfo
from neonize.utils.enum import ChatPresence, ChatPresenceMedia
from neonize.utils.message import extract_text

from bot import (
    JID,
    Message,
    MessageEv,
    NewAClient,
    SendResponse,
    base_msg,
    base_msg_info,
    base_msg_source,
    jid,
)
from bot.config import bot, conf

from .log_utils import logger


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

        def construct(self, message: MessageEv, alt=False):
            self.name = message.Info.Pushname
            self.jid = (
                message.Info.MessageSource.Sender
                if not alt
                else message.Info.MessageSource.SenderAlt
            )
            self.id = self.jid.User
            self.is_empty = self.jid.IsEmpty
            self.server = self.jid.Server
            self.is_hidden = self.server == "lid"

    class Chat:
        def __init__(self):
            self.name = None

        def construct(self, msg_source: base_msg_source):
            self.jid = msg_source.Chat
            self.id = self.jid.User
            self.is_empty = msg_source.Chat.IsEmpty
            self.is_group = msg_source.IsGroup
            self.server = self.jid.Server

    def _construct_media(self):
        for msg, v in self._message.ListFields():
            if not msg.name.endswith("ContextInfo"):
                self.name = msg.name
            if not msg.name.endswith("Message"):
                continue
            setattr(self, msg.name.split("M")[0], v)
            if not hasattr(v, "contextInfo"):
                continue
            self.media = v
            break

    def _populate(self):
        attrs = [
            "audio",
            "document",
            "image",
            "media",
            "protocol",
            "reaction",
            "video",
            "sticker",
        ]
        attrs.extend(["lid_address", "revoked_id"])
        attrs.extend(["pollUpdate", "senderKeyDistribution"])
        for a in attrs:
            setattr(self, a, None)

    def construct(self, message: MessageEv, add_replied: bool = True):
        self.chat = self.Chat()
        self.chat.construct(message.Info.MessageSource)
        self.alt_user = self.User()
        self.alt_user.construct(message, alt=True)
        self.user = self.User()
        self.user.construct(message)

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
        self.timestamp = self.message.Info.Timestamp
        # mention_str = f"@{(self.w_id.split('@'))[0]}"
        # self.mentioned = self.text.startswith(mention_str) if self.text else False
        # if self.mentioned:
        #    self.text = (self.text.split(maxsplit=1)[1]).strip()
        self.text = self.text or self.short_text or None
        self._populate()
        self._construct_media()
        self.is_revoke = False
        if self.protocol and self.protocol.type == 0:
            self.is_revoke = True
            self.revoked_id = self.protocol.key.ID
        if self.message.Info.MessageSource.AddressingMode == 2:
            self.lid_address = True
        self.from_user = copy.deepcopy(self.alt_user if self.lid_address else self.user)
        self.from_user.hid = self.user.id if self.lid_address else self.alt_user.id
        self.from_user.lid = self.user.jid if self.lid_address else self.alt_user.jid
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
        if self.outgoing:
            if self.lid_address:
                patch_msg_sender(self.message, self.user.jid, bot.me.JID)
                self.from_user.jid = bot.me.JID
                self.from_user.id = bot.me.JID.User
                self.from_user.hid = self.user.id
            else:
                patch_msg_sender(self.message, self.user.jid, bot.me.LID)
                self.from_user.jid = bot.me.LID
                self.from_user.id = bot.me.LID.User
                self.from_user.hid = self.user.id
        self.constructed = True
        return self

    async def _send_message(
        self,
        chat,
        message,
        link_preview: bool = True,
        ghost_mentions: str = None,
        mentions_are_lids: bool = False,
        add_msg_secret: bool = False,
    ):
        await self.send_typing_status()
        response = await self.client.send_message(
            to=chat,
            message=message,
            link_preview=link_preview,
            ghost_mentions=ghost_mentions,
            mentions_are_lids=mentions_are_lids or self.lid_address,
            add_msg_secret=add_msg_secret,
        )
        await self.send_typing_status(False)
        msg = self.gen_new_msg(response)
        return construct_event(msg)

    async def delete(self):
        await self.client.revoke_message(self.chat.jid, self.from_user.jid, self.id)
        return

    async def edit(self, text: str):
        msg = Message(conversation=text)
        response = await self.client.edit_message(self.chat.jid, self.id, msg)
        msg = self.gen_new_msg(response)
        return construct_event(msg)

    async def react(self, emoji: str):
        reaction = await self.client.build_reaction(
            self.chat.jid, self.from_user.jid, self.id, emoji
        )
        return await self.client.send_message(self.chat.jid, reaction)

    async def reply(
        self,
        text: str = None,
        to: JID = None,
        file: str | bytes = None,
        file_name: str = None,
        image: str = None,
        quote: bool = True,
        link_preview: bool = True,
        reply_privately: bool = False,
        ghost_mentions: str = None,
        message: MessageWithContextInfo = None,
        mentions_are_lids: bool = False,
        add_msg_secret: bool = False,
    ):
        if not self.constructed:
            return
        if file:
            return await self.reply_document(
                file, file_name, text, quote, ghost_mentions=ghost_mentions
            )
        if image and file_name:
            return await self.reply_photo(
                image, text, quote, ghost_mentions=ghost_mentions
            )
        text = text or message
        if not text:
            raise Exception("Specify a text to reply with.")
        # msg_id = self.id if quote else None
        if not quote:
            return await self._send_message(
                self.chat.jid, text, link_preview, ghost_mentions=ghost_mentions
            )
        await self.send_typing_status()

        try:
            response = await self.client.reply_message(
                text,
                copy.deepcopy(self.message),
                to=to,
                link_preview=link_preview,
                reply_privately=reply_privately,
                ghost_mentions=ghost_mentions,
                mentions_are_lids=mentions_are_lids or self.lid_address,
                add_msg_secret=add_msg_secret,
            )
        except httpx.HTTPStatusError:
            await logger(Exception)
            response = await self.client.reply_message(
                text,
                copy.deepcopy(self.message),
                to=to,
                link_preview=False,
                reply_privately=reply_privately,
                ghost_mentions=ghost_mentions,
                mentions_are_lids=mentions_are_lids or self.lid_address,
                add_msg_secret=add_msg_secret,
            )
        # self.id = response.ID
        # self.text = text
        # new_jid = jid.build_jid(conf.PHNUMBER)
        # self.user.jid = new_jid
        # self.user.id = new_jid.User

        # self.user.name = None
        await self.send_typing_status(False)
        msg = self.gen_new_msg(response, private=reply_privately)
        return construct_event(msg)

    async def reply_audio(
        self,
        audio: str | bytes,
        ptt: bool = False,
        quote: bool = True,
        add_msg_secret: bool = False,
    ):
        quoted = copy.deepcopy(self.message) if quote else None

        response = await self.client.send_audio(
            self.chat.jid, audio, ptt, quoted=quoted, add_msg_secret=add_msg_secret
        )
        msg = self.gen_new_msg(response)
        return construct_event(msg)

    async def reply_document(
        self,
        document: str | bytes,
        file_name: str = None,
        caption: str = None,
        quote: bool = True,
        ghost_mentions: str = None,
        mentions_are_lids: bool = False,
        add_msg_secret: bool = False,
    ):
        quoted = copy.deepcopy(self.message) if quote else None
        _, file_name = (
            os.path.split(document)
            if not file_name and isinstance(document, str)
            else (None, file_name)
        )
        response = await self.client.send_document(
            self.chat.jid,
            document,
            caption,
            filename=file_name,
            quoted=quoted,
            ghost_mentions=ghost_mentions,
            mentions_are_lids=mentions_are_lids or self.lid_address,
            add_msg_secret=add_msg_secret,
        )
        msg = self.gen_new_msg(response)
        return construct_event(msg)

    async def reply_gif(
        self,
        gif: str | bytes,
        caption: str = None,
        quote: bool = True,
        viewonce: bool = False,
        as_gif: bool = True,
        ghost_mentions: str = None,
        mentions_are_lids: bool = False,
        add_msg_secret: bool = False,
    ):
        quoted = copy.deepcopy(self.message) if quote else None
        response = await self.client.send_video(
            self.chat.jid,
            gif,
            caption,
            quoted=quoted,
            viewonce=viewonce,
            gifplayback=as_gif,
            is_gif=True,
            ghost_mentions=ghost_mentions,
            mentions_are_lids=mentions_are_lids or self.lid_address,
            add_msg_secret=add_msg_secret,
        )
        msg = self.gen_new_msg(response)
        return construct_event(msg)

    async def reply_photo(
        self,
        photo: str | bytes,
        caption: str = None,
        quote: bool = True,
        viewonce: bool = False,
        ghost_mentions: str = None,
        mentions_are_lids: bool = False,
        add_msg_secret: bool = False,
    ):
        quoted = copy.deepcopy(self.message) if quote else None
        response = await self.client.send_image(
            self.chat.jid,
            photo,
            caption,
            quoted=quoted,
            viewonce=viewonce,
            ghost_mentions=ghost_mentions,
            mentions_are_lids=mentions_are_lids or self.lid_address,
            add_msg_secret=add_msg_secret,
        )
        msg = self.gen_new_msg(response)
        return construct_event(msg)

    async def reply_sticker(
        self,
        file: str | bytes,
        quote: bool = True,
        name: str = "",
        packname: str = "",
        crop: bool = False,
        enforce_not_broken: bool = False,
        add_msg_secret: bool = False,
    ):
        quoted = copy.deepcopy(self.message) if quote else None
        response = await self.client.send_sticker(
            self.chat.jid,
            file,
            quoted=quoted,
            name=name,
            packname=packname,
            crop=crop,
            enforce_not_broken=enforce_not_broken,
            add_msg_secret=add_msg_secret,
        )
        msg = self.gen_new_msg(response)
        return construct_event(msg)

    async def reply_video(
        self,
        video: str | bytes,
        caption: str = None,
        quote: bool = True,
        viewonce: bool = False,
        as_gif: bool = False,
        ghost_mentions: str = None,
        mentions_are_lids: bool = False,
        add_msg_secret: bool = False,
    ):
        quoted = copy.deepcopy(self.message) if quote else None
        response = await self.client.send_video(
            self.chat.jid,
            video,
            caption,
            quoted=quoted,
            viewonce=viewonce,
            gifplayback=as_gif,
            ghost_mentions=ghost_mentions,
            mentions_are_lids=mentions_are_lids or self.lid_address,
            add_msg_secret=add_msg_secret,
        )
        msg = self.gen_new_msg(response)
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

    def gen_new_msg(self, response: SendResponse, private=False):
        msg = copy.deepcopy(self.message)
        msg.Info.ID = response.ID
        msg.Info.Pushname = bot.me.PushName
        msg.Info.Timestamp = response.Timestamp
        patch_msg(msg, response.Message)
        if private:
            msg.Info.MessageSource.Chat.User = self.from_user.id
            msg.Info.MessageSource.Chat.Server = self.from_user.server
        if self.lid_address:
            patch_msg_sender(msg, bot.me.LID, bot.me.JID)
        else:
            patch_msg_sender(msg, bot.me.JID, bot.me.LID)
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
            (self.quoted.participant.split("@"))[1],
            self.quoted.quotedMessage,
        )
        return construct_event(msg, False)


POLL = 1
function_dict = {None: []}
anti_duplicate = deque(maxlen=10)


def register(key: str | None = None):
    def dec(fn):
        nonlocal key
        if isinstance(key, int):
            function_dict.update({key: fn})
        elif not key:
            function_dict[key].append(fn)
        else:
            key = conf.CMD_PREFIX + key
            function_dict.update({key: fn})

    return dec


def add_handler(function, command: str | None = None, **kwargs):
    if command:

        async def _(client: NewAClient, event: Event):
            await event_handler(event, function, client, **kwargs)

    else:

        async def _(client: NewAClient, event: Event):
            await function(event, None, client)

    register(command)(_)


bot.add_handler = add_handler
bot.register = register


async def handler_helper(funcs):
    await asyncio.sleep(0.1)
    await asyncio.gather(*funcs)


async def on_message(client: NewAClient, message: MessageEv):
    try:
        # await logger(e=message)
        event = construct_event(message)
        if event.pollUpdate:
            future = asyncio.run_coroutine_threadsafe(
                function_dict[POLL](client, event), bot.loop
            )
            return future.result()

        _id = f"{event.name}:{event.chat.id}:{event.id}"
        if _id in anti_duplicate:
            return
        anti_duplicate.append(_id)
        bot.pending_saved_messages.append(event)
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
        if not function_dict[None]:
            return
        func_list = [func(client, event) for func in function_dict[None]]
        future = asyncio.run_coroutine_threadsafe(handler_helper(func_list), bot.loop)
        future.result()
    except Exception:
        await logger(e="Unhandled Exception:")
        await logger(Exception)


def construct_event(message: MessageEv, add_replied=True):
    msg = Event()
    return msg.construct(message, add_replied=add_replied)


def construct_message(
    chat_id,
    user_id,
    msg_id,
    text,
    server="s.whatsapp.net",
    userver="s.whatsapp.net",
    Msg=None,
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
                Sender=jid.build_jid(user_id, userver),
            ),
        ),
    )


def construct_msg_and_evt(*args, **kwargs):
    return construct_event(construct_message(*args, **kwargs))


def patch_msg(msg: Message, new_msg: Message):
    temp_msg = msg.__class__(
        Message=new_msg,
        Raw=new_msg,
    )
    msg.Message.Clear()
    msg.Raw.Clear()
    msg.MergeFrom(temp_msg)


def patch_msg_sender(msg: Message, sender: JID, sender_alt: JID):
    msg.Info.MessageSource.MergeFrom(
        msg.Info.MessageSource.__class__(
            Sender=sender,
            SenderAlt=sender_alt,
        )
    )


async def event_handler(
    event: Event,
    function,
    client: NewAClient | None = None,
    require_args: bool = False,
    disable_help: bool = False,
    split_args: str = " ",
    default_args: str = False,
    use_default_args: str | None | bool = False,
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
