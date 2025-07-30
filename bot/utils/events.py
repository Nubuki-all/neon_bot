from __future__ import annotations

import asyncio
import copy
import inspect
import os
import warnings
from collections import deque
from collections.abc import Callable

import httpx
from neonize.types import MessageWithContextInfo
from neonize.utils.enum import ChatPresence, ChatPresenceMedia, MediaType
from neonize.utils.message import extract_text, get_message_type

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
from bot.types.event import BaseEvent, Chat, User

from .bot_utils import write_binary
from .log_utils import logger


class Event(BaseEvent):
    def __init__(self):
        super().__init__()
        self.client = bot.client
        self.chat = Chat()
        self.user = User()
        self.alt_user = User()

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "client":
                v = None
            setattr(result, k, copy.deepcopy(v, memo))
        return result

    def _construct_media(self, message=None):
        for msg, v in (message or self._message).ListFields():
            if not msg.name.endswith("ContextInfo"):
                if not message:
                    self.name = self.short_name = msg.name
            if msg.name.startswith("viewOnce"):
                self.short_name = "viewOnce"
                self.view_once = v
                return self._construct_media(self.view_once.message)
            if not msg.name.endswith("Message"):
                continue
            s_name = msg.name.split("M")[0]
            setattr(self, s_name, v)
            if not message:
                self.short_name = s_name
            if not hasattr(v, "contextInfo"):
                continue
            self.media = v
            break

    def construct(self, message: MessageEv, add_replied: bool = True) -> Event:
        self.message = message
        msg_info = message.Info
        msg_source = msg_info.MessageSource
        self.outgoing = msg_source.IsFromMe
        if msg_source.AddressingMode == 2:
            self.lid_address = True

        # Patch message if it was sent by current user on another device
        if self.outgoing:
            if msg_source.Sender.Server == "lid":
                patch_msg_sender(
                    message,
                    msg_source.Sender,
                    bot.client.me.JID,
                )
            else:
                patch_msg_sender(
                    message,
                    msg_source.Sender,
                    bot.client.me.LID,
                )
        self.chat.construct(msg_source)
        self.alt_user.construct(msg_info, alt=True)
        self.user.construct(msg_info)

        # To do support other message types
        self.id = msg_info.ID
        self.type = msg_info.Type
        self.type = "text" if msg_info.MediaType == "url" else self.type
        self.media_type = msg_info.MediaType
        self._message = message.Message
        self._ext_msg = message.Message.extendedTextMessage
        self._text_msg = message.Message.conversation
        self._short_text = self._text_msg
        self.text = self._ext_msg.text
        self.timestamp = msg_info.Timestamp
        self.text = self.text or self._short_text or None
        self._construct_media()

        if self.protocol:
            if self.protocol.type == 0:
                self.is_revoke = True
                self.revoked_id = self.protocol.key.ID
            if self.protocol.type == 14:
                self.is_edit = True
                self.edited_id = self.protocol.key.ID
                if self.protocol.editedMessage.conversation:
                    self.text = self.protocol.editedMessage.conversation
                else:
                    self.text = (
                        self.protocol.editedMessage.extendedTextMessage.text or None
                    )
                    self._construct_media(self.protocol.editedMessage)
                    self.caption = (
                        extract_text(self.protocol.editedMessage)
                        if not self.text
                        else None
                    )

        self.from_user = copy.deepcopy(self.alt_user if self.lid_address else self.user)
        self.from_user.hid = self.user.id if self.lid_address else self.alt_user.id
        self.from_user.lid = self.user.jid if self.lid_address else self.alt_user.jid
        self.caption = (
            (extract_text(self._message) or None)
            if not (self.text or self.is_edit)
            else self.caption
        )
        if media := (self.audio or self.image or self.ptv or self.video):
            self.is_actual_media = True
            self.is_view_once = media.viewOnce
        if self.media:
            self.message_association = (
                self._message.messageContextInfo.messageAssociation
            )
            if self.message_association.associationType == 1:
                self.is_album = True
                self.album_id = self.message_association.parentMessageKey.ID

        self._context_info = (
            self.media.contextInfo
            if add_replied and self.media and self.media.contextInfo.ByteSize()
            else None
        )
        self.reply_to_message = self.get_replied_msg()
        self.is_status = msg_source.Chat.User.casefold() == "status"
        self.constructed = True
        return self

    async def _react(self, emoji: str):
        reaction = await self.client.build_reaction(
            self.chat.jid, self.from_user.jid, self.id, emoji
        )
        return await self.client.send_message(self.chat.jid, reaction)

    def _get_quoted(self) -> MessageEv:
        if not (self.media or self.text):
            return
        quoted = copy.deepcopy(self.message)
        if self.is_edit:
            quoted.Info.ID = self.edited_id
            patch_msg(quoted, copy.deepcopy(self.protocol.editedMessage))
        return quoted

    async def _send_message(
        self,
        chat,
        message,
        link_preview: bool = True,
        ghost_mentions: str = None,
        mentions_are_lids: bool = False,
        mentions_are_jids: bool = False,
        add_msg_secret: bool = False,
    ) -> Event:
        mentions_are_not_jids = False if mentions_are_jids else self.lid_address
        if not isinstance(message, str):
            field_name = (
                message.__class__.__name__[0].lower() + message.__class__.__name__[1:]
            )
            message = Message(**{field_name: message})
        await self.send_typing_status()
        response = await self.client.send_message(
            to=chat,
            message=message,
            link_preview=link_preview,
            ghost_mentions=ghost_mentions,
            mentions_are_lids=mentions_are_lids or mentions_are_not_jids,
            add_msg_secret=add_msg_secret,
        )
        await self.send_typing_status(False)
        msg = self.gen_new_msg(response)
        return construct_event(msg)

    async def delete(self):
        await self.client.revoke_message(self.chat.jid, self.from_user.jid, self.id)
        return

    async def download(self, path: str = None) -> bytes | None:
        if not (
            self.audio or self.document or self.image or self.sticker or self.video
        ):
            raise Exception("Not a downloadable event!")
        bytes_ = await download_media(self._message)
        if not path:
            return bytes_
        await write_binary(path, bytes_)

    async def edit(self, text: str = None, message=None) -> Event:
        msg = Message(conversation=text) if text else message
        response = await self.client.edit_message(self.chat.jid, self.id, msg)
        msg = self.gen_new_msg(response)
        return construct_event(msg)

    async def _send_reaction(self, emoji: str) -> Event:
        """Internal method to send a reaction."""
        reaction = await self.client.build_reaction(
            self.chat.jid, self.from_user.jid, self.id, emoji
        )
        return await self.client.send_message(self.chat.jid, reaction)

    def react(self, emoji: str):
        """Returns a context manager for async with or can be awaited directly."""
        return self.ReactionContext(self, emoji)

    class ReactionContext:
        def __init__(self, event, emoji):
            self.event = event
            self.emoji = emoji
            self._used = False  # Track if context was properly used

        async def _react(self):
            """Send the reaction and mark it as active."""
            await self.event._react(self.emoji)

        async def _remove(self):
            """Remove the reaction if it was sent."""
            await self.event._react("")

        async def __aenter__(self):
            """Enter context: send reaction."""
            self._used = True
            await self._react()
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            """Exit context: remove reaction."""
            await self._remove()

        def __await__(self):
            """Allow direct awaiting: send reaction without removal."""
            self._used = True
            return self._react().__await__()

        def __del__(self):
            """Warn if context was created but never used."""
            if not self._used:
                warnings.warn(
                    "ReactionContext was created but never used. "
                    "Did you forget 'await' or 'async with'?",
                    RuntimeWarning,
                    stacklevel=3,  # Points to the original react() call site
                )

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
        mentions_are_jids: bool = False,
        add_msg_secret: bool = False,
    ) -> Event:
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
        text = text or copy.deepcopy(message)
        if not text:
            raise Exception("Specify a text to reply with.")
        quoted = self._get_quoted() if quote else None
        if not quoted:
            return await self._send_message(
                self.chat.jid,
                text,
                link_preview,
                ghost_mentions=ghost_mentions,
                mentions_are_lids=mentions_are_lids,
                mentions_are_jids=mentions_are_jids,
                add_msg_secret=add_msg_secret,
            )
        mentions_are_not_jids = False if mentions_are_jids else self.lid_address

        await self.send_typing_status()
        try:
            response = await self.client.reply_message(
                text,
                quoted,
                to=to,
                link_preview=link_preview,
                reply_privately=reply_privately,
                ghost_mentions=ghost_mentions,
                mentions_are_lids=mentions_are_lids or mentions_are_not_jids,
                add_msg_secret=add_msg_secret,
            )
        except httpx.HTTPStatusError:
            await logger(Exception)
            response = await self.client.reply_message(
                text,
                quoted,
                to=to,
                link_preview=False,
                reply_privately=reply_privately,
                ghost_mentions=ghost_mentions,
                mentions_are_lids=mentions_are_lids or mentions_are_not_jids,
                add_msg_secret=add_msg_secret,
            )
        await self.send_typing_status(False)
        msg = self.gen_new_msg(response, private=reply_privately)
        return construct_event(msg)

    async def reply_album(
        self,
        files: list,
        caption: str = None,
        quote: bool = True,
        ghost_mentions: str = None,
        mentions_are_lids: bool = False,
        mentions_are_jids: bool = False,
        add_msg_secret: bool = False,
    ) -> Event:
        quoted = self._get_quoted() if quote else None
        mentions_are_not_jids = False if mentions_are_jids else self.lid_address
        responses = await self.client.send_album(
            self.chat.jid,
            files,
            caption,
            quoted=quoted,
            ghost_mentions=ghost_mentions,
            mentions_are_lids=mentions_are_lids or mentions_are_not_jids,
            add_msg_secret=add_msg_secret,
        )
        msg = self.gen_new_msg(responses[0])
        return construct_event(msg)

    async def reply_audio(
        self,
        audio: str | bytes,
        ptt: bool = False,
        quote: bool = True,
        add_msg_secret: bool = False,
    ) -> Event:
        quoted = self._get_quoted() if quote else None

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
        mentions_are_jids: bool = False,
        add_msg_secret: bool = False,
    ) -> Event:
        quoted = self._get_quoted() if quote else None
        _, file_name = (
            os.path.split(document)
            if not file_name and isinstance(document, str)
            else (None, file_name)
        )
        mentions_are_not_jids = False if mentions_are_jids else self.lid_address
        response = await self.client.send_document(
            self.chat.jid,
            document,
            caption,
            filename=file_name,
            quoted=quoted,
            ghost_mentions=ghost_mentions,
            mentions_are_lids=mentions_are_lids or mentions_are_not_jids,
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
        mentions_are_jids: bool = False,
        add_msg_secret: bool = False,
    ) -> Event:
        quoted = self._get_quoted() if quote else None
        mentions_are_not_jids = False if mentions_are_jids else self.lid_address
        response = await self.client.send_video(
            self.chat.jid,
            gif,
            caption,
            quoted=quoted,
            viewonce=viewonce,
            gifplayback=as_gif,
            is_gif=True,
            ghost_mentions=ghost_mentions,
            mentions_are_lids=mentions_are_lids or mentions_are_not_jids,
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
        mentions_are_jids: bool = False,
        add_msg_secret: bool = False,
    ) -> Event:
        quoted = self._get_quoted() if quote else None
        mentions_are_not_jids = False if mentions_are_jids else self.lid_address
        response = await self.client.send_image(
            self.chat.jid,
            photo,
            caption,
            quoted=quoted,
            viewonce=viewonce,
            ghost_mentions=ghost_mentions,
            mentions_are_lids=mentions_are_lids or mentions_are_not_jids,
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
        animated_gif: bool = False,
        passthrough: bool = False,
        add_msg_secret: bool = False,
    ) -> Event:
        quoted = self._get_quoted() if quote else None
        response = await self.client.send_sticker(
            self.chat.jid,
            file,
            quoted=quoted,
            name=name,
            packname=packname,
            crop=crop,
            enforce_not_broken=enforce_not_broken,
            animated_gif=animated_gif,
            passthrough=passthrough,
            add_msg_secret=add_msg_secret,
        )
        msg = self.gen_new_msg(response)
        return construct_event(msg)

    async def reply_stickerpack(
        self,
        files: list,
        quote: bool = True,
        packname: str = "",
        publisher: str = "",
        crop: bool = False,
        animated_gif: bool = False,
        passthrough: bool = False,
        add_msg_secret: bool = False,
    ) -> Event:
        quoted = self._get_quoted() if quote else None
        responses = await self.client.send_stickerpack(
            self.chat.jid,
            files,
            quoted=quoted,
            packname=packname,
            publisher=publisher,
            crop=crop,
            animated_gif=animated_gif,
            passthrough=passthrough,
            add_msg_secret=add_msg_secret,
        )
        msg = self.gen_new_msg(responses[-1])
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
        mentions_are_jids: bool = False,
        add_msg_secret: bool = False,
    ) -> Event:
        quoted = self._get_quoted() if quote else None
        mentions_are_not_jids = False if mentions_are_jids else self.lid_address
        response = await self.client.send_video(
            self.chat.jid,
            video,
            caption,
            quoted=quoted,
            viewonce=viewonce,
            gifplayback=as_gif,
            ghost_mentions=ghost_mentions,
            mentions_are_lids=mentions_are_lids or mentions_are_not_jids,
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

    def gen_new_msg(self, response: SendResponse, private=False) -> MessageEv:
        msg = copy.deepcopy(self.message)
        msg.Info.ID = response.ID
        msg.Info.Pushname = bot.client.me.PushName
        msg.Info.Timestamp = response.Timestamp
        patch_msg(msg, response.Message)
        if private:
            msg.Info.MessageSource.Chat.User = self.from_user.id
            msg.Info.MessageSource.Chat.Server = self.from_user.server
        if self.lid_address:
            patch_msg_sender(msg, bot.client.me.LID, bot.client.me.JID)
        else:
            patch_msg_sender(msg, bot.client.me.JID, bot.client.me.LID)
        return msg

    def get_replied_msg(self) -> Event:
        if not (self._context_info and self._context_info.stanzaID):
            return
        if self._context_info.remoteJID:
            chat_id, server = self._context_info.remoteJID.split("@", maxsplit=1)
        else:
            chat_id = self.chat.id
            server = self.chat.server
        msg = construct_message(
            chat_id,
            (self._context_info.participant.split("@"))[0],
            self._context_info.stanzaID,
            None,
            server,
            (self._context_info.participant.split("@"))[1],
            self._context_info.quotedMessage,
        )
        return construct_event(msg, False)


POLL = 1
function_dict = {None: []}
anti_duplicate = deque(maxlen=10000)


def register(key: str | None = None):
    """A decorator to register event handlers"""

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
    """Adds an handler using the register decorator"""
    if command:

        async def _(client: NewAClient, event: Event):
            await event_handler(event, function, client, **kwargs)

    else:

        async def _(client: NewAClient, event: Event):
            await function(event, None, client)

    register(command)(_)
    return _


def unregister(key: str | Callable):
    """Unregisters an event handler"""
    if isinstance(key, str):
        key = conf.CMD_PREFIX + key
        function_dict.pop(key)
    else:
        function_dict[None].remove(key)


bot.add_handler = add_handler
bot.register = register
bot.unregister = unregister


async def handler_helper(funcs):
    await asyncio.sleep(0.1)
    await asyncio.gather(*funcs)


async def on_message(client: NewAClient, message: MessageEv):
    try:
        # await logger(e=message)
        event = construct_event(message)
        if event.pollUpdate:
            return await function_dict[POLL](client, event)

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
                await func(client, event)
        if not function_dict[None]:
            return
        funcs = [func(client, event) for func in function_dict[None]]
        await asyncio.gather(*funcs)
    except Exception:
        await logger(e="Unhandled Exception(s):", error=True)
        await logger(Exception)


def construct_event(message: MessageEv, add_replied=True) -> Event:
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
    user_id2=None,
    userver2="lid",
) -> MessageEv:
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
                SenderAlt=jid.build_jid(user_id2, userver2) if user_id2 else None,
            ),
        ),
    )


def construct_msg_and_evt(*args, **kwargs) -> Event:
    return construct_event(construct_message(*args, **kwargs))


def patch_msg(msg: MessageEv, new_msg: Message):
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


async def download_media(message: Message) -> bytes:
    item = get_message_type(message)
    media_type = MediaType.from_message(message)

    direct_path = item.directPath
    enc_file_hash = item.fileEncSHA256
    file_hash = item.fileSHA256
    media_key = item.mediaKey
    file_length = item.fileLength
    mms_type = media_type.to_mms()
    return await bot.client.download_media_with_path(
        direct_path,
        enc_file_hash,
        file_hash,
        media_key,
        file_length,
        media_type,
        mms_type,
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
    replace_args=None,
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
    args = replace_args or args
    await function(event, args, client)
