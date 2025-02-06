import asyncio
import copy
import io
import random

import torch
from clean_links.clean import clean_url
from neonize.exc import DownloadError
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (
    DeviceListMetadata,
    FutureProofMessage,
    InteractiveMessage,
    Message,
    MessageContextInfo,
)
from PIL import Image
from RealESRGAN import RealESRGAN
from urlextract import URLExtract

from bot.config import bot, conf
from bot.fun.quips import enquip, enquip4
from bot.fun.stickers import ran_stick
from bot.utils.bot_utils import (
    png_to_jpg,
    split_text,
    sync_to_async,
    turn,
    wait_for_turn,
    waiting_for_turn,
)
from bot.utils.db_utils import save2db2
from bot.utils.log_utils import logger
from bot.utils.msg_utils import (
    Message,
    chat_is_allowed,
    clean_reply,
    download_replied_media,
    get_args,
    tag_admins,
    user_is_admin,
    user_is_allowed,
    user_is_owner,
    user_is_privileged,
)


async def sticker_reply(event, args, client, overide=False):
    """
    Sends a random sticker upon being tagged
    """
    try:
        if event.type != "text":
            return
        if not overide:
            if not event.text.startswith("@"):
                return
            me = await bot.client.get_me()
            if not event.text.startswith("@" + me.JID.User):
                return
        else:
            me = await bot.client.get_me()
        reply = (
            event.reply_to_message
            if len(event.text.split()) == 1 and not overide
            else event
        )
        await event.send_typing_status()
        random_sticker = ran_stick()
        await clean_reply(
            event,
            reply,
            "reply_sticker",
            random_sticker,
            quote=True,
            name=random.choice((enquip(), enquip4())),
            packname=me.PushName,
        )
        await event.send_typing_status(False)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def sanitize_url(event, args, client):
    """
    Checks and sanitizes all links in replied message

    Can also receive a link as argument
    """
    status_msg = None
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not (event.quoted_text or args):
            return await event.reply(f"{sanitize_url.__doc__}")
        status_msg = await event.reply("Please wait…")
        extractor = URLExtract()
        if event.quoted_text:
            msg = event.quoted_text
            urls = extractor.find_urls(msg)
            if not urls:
                return await event.reply(
                    f"*No link found in @{event.reply_to_message.from_user.id}'s message to sanitize*"
                )
            new_msg = msg
            sanitized_links = []
            for url in urls:
                sanitized_links.append(clean_url(url))
            for a, b in zip(urls, sanitized_links):
                new_msg = new_msg.replace(a, b)
            return await clean_reply(event, event.reply_to_message, "reply", new_msg)
        urls = extractor.find_urls(args)
        if not urls:
            return await event.reply(f"*No link found in your message to sanitize*")
        msg = "*Sanitized link(s):*"
        for url in urls:
            msg += f"\n\n{url}"
        return await clean_reply(event, event.reply_to_message, "reply", msg)
    except Exception:
        await logger(Exception)
        await event.react("❌")
    finally:
        if status_msg:
            await status_msg.delete()


async def stickerize_image(event, args, client):
    """
    Turns replied image to sticker.
    Args:
        Name of sticker
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if args:
            arg, args = get_args(
                ["-f", "store_false"],
                ["-c", "store_true"],
                to_parse=args,
                get_unknown=True,
            )
            crop = arg.c
            forced = arg.f
        else:
            crop = False
            forced = True

        if not (event.quoted_image or event.quoted_video):
            return await event.reply("*Replied message is not a gif/image/video.*")

        # forced = False if event.quoted_image else forced
        await event.send_typing_status()
        file = await download_replied_media(event)
        me = await bot.client.get_me()
        return await event.reply_sticker(
            file,
            quote=True,
            name=(args or random.choice((enquip(), enquip4()))),
            packname=me.PushName,
            crop=crop,
            enforce_not_broken=forced,
        )
        await event.send_typing_status(False)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def upscale_image(event, args, client):
    """
    Upscales replied image.
    Args:
        None yet.
    """
    status_msg = None
    turn_id = f"{event.chat.id}:{event.id}"
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if bot.disable_cic:
            return await event.reply("*CPU heavy commands are currently disabled.*")
        quoted_msg = event.quoted.quotedMessage
        if not quoted_msg.imageMessage.URL:
            return await event.reply(
                "*Command can only be used when replying to an image.*"
            )
        if quoted_msg.imageMessage.fileLength > 17939583:
            return await sticker_reply(event, args, client, True)
        turn().append(turn_id)
        status_msg = await event.reply("*…*")
        if event.quoted_image.caption.startswith("Upscaled image:"):
            return await event.reply(
                "What?, initial upscale not good enough for you? 😒"
            )
        file = await download_replied_media(event)

        if waiting_for_turn():
            await event.react("⏰")
            w_msg = await status_msg.edit(
                "*Waiting till previous upscaling process gets completed.*"
            )
            await wait_for_turn(turn_id)
            await event.react("")
        # async with heavy_proc_lock:
        # Lock works now but eh i like the current implementation better
        await status_msg.edit("*Upscaling please wait…*")
        device = torch.device(
            "cuda" if torch.cuda.is_available() and not conf.NO_GPU else "cpu"
        )
        model = RealESRGAN(device, scale=4)
        model.load_weights("weights/RealESRGAN_x4.pth", download=True)
        image = Image.open(io.BytesIO(file)).convert("RGB")
        sr_image = await sync_to_async(model.predict, image)
        output = io.BytesIO()
        sr_image.save(output, format="png")
        output.name = f"upscaled_image.png"
        raw = output.getvalue()
        msg = await event.reply_photo(raw, "Upscaled image: Raw")
        raw = await png_to_jpg(raw)
        await msg.reply_photo(raw, "Upscaled image: Jpeg")
    except Exception as e:
        await logger(Exception)
        await event.react("❌")
        await status_msg.edit(f"*Error:*\n{e}")
        status_msg = None
    finally:
        if turn(turn_id):
            turn().pop(0)
        if status_msg:
            await status_msg.delete()


async def pick_random(event, args, client):
    """
    A randomizer;
    Select a random or multiple random values from a list (replied message).
    Arguments:
        -a: Amount of values to select
        -m: Message header for returned values; can add without specifying -m
        -s: Change delimiter, default="\\n" (new lines)

    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not event.quoted_text:
            return await event.reply(
                "*Reply to a message with list of items to choose from.*"
            )
        arg, args = get_args(
            "-a",
            "-m",
            "-s",
            to_parse=(args or str()),
            get_unknown=True,
        )
        items = event.quoted_text.split((arg.s or "\n"))
        if len(items) < 2:
            return await event.reply("I need more options to choose from.")
        if arg.a:
            if not arg.a.isdigit():
                return await event.reply("-a: value has to be a digit.")
            arg.a = int(arg.a)
        args = arg.m or args
        out = random.sample(items, (arg.a or 1))
        msg = list_items(out, (args or "*Selected:*"))
        await event.reply(msg)
    except Exception:
        await logger(Exception)
        await event.react("❌")


def list_items(items, ini):
    msg = f"{ini}\n"
    for item in items:
        msg += f"*⁍* {item.strip()}\n"
    return msg


async def list_notes(event, args, client):
    """
    Fetches the list of notes in a chat:
    Arguments: [None]
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        chat = event.chat.id
        chat_name = (
            (await bot.client.get_group_info(event.chat.jid)).GroupName.Name
            if event.chat.is_group
            else "Pm"
        )
        if not (notes := bot.notes_dict.get(chat)):
            return await event.reply(f"*No notes found for chat: {chat_name}!*")
        reply = await event.reply("_Fetching notes…_")
        filter_ = True if args and args.casefold() in ("my notes", "me") else False
        msg = f"*{'Your l' if filter_ else 'L'}ist of notes in {chat_name}*"
        msg_ = str()
        i = 1
        for title in list(notes.keys()):
            if filter_ and notes[title].get("user") != user:
                continue
            user_name = notes[title].get("user_name")
            msg_ += f"\n{i}. *{title}*{f' added by *{user_name}*' if event.chat.is_group and not filter_ else str()}"
            i += 1
        if not msg_:
            return await event.reply(
                f"*You currently have no saved notes in {chat_name}*!"
            )
        msg += msg_

        chain_reply = None
        for text in split_text(msg):
            chain_reply = (
                await reply.edit(text)
                if not chain_reply
                else await chain_reply.reply(text)
            )
            await asyncio.sleep(2)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def save_notes(event, args, client):
    """
    Saves a replied Text/media message to bot database;
    Can be retrieved with get {note_name}
    Argument:
        note_name: name to save note as
        -c: clean caption
    """
    chat = event.chat.id
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not event.quoted_msg:
            return await event.reply("Can only save replied text or media.")
        if args.casefold() in ("all", "notes", "my notes", "me"):
            return await event.reply(f"Given note_name *{args}* is blocked.")
        if not bot.notes_dict.get(chat):
            bot.notes_dict[chat] = {}
        if (notes := bot.notes_dict[chat]).get(args):
            if not user_is_owner(user) and user != notes[args]["user"]:
                return await event.reply(
                    f"Note with name '{args}' already exists and can't be overwritten; Most likely because *you* did not add it."
                )
        arg, args = get_args(
            ["-c", "store_true"],
            to_parse=args,
            get_unknown=True,
        )
        status_msg = await event.reply("…")
        # note gen:
        note_type = str
        if event.quoted_text:
            note = event.quoted_text
        elif event.quoted_image:
            if event.quoted_image.fileLength < 5000000:
                note = await download_replied_media(event)
                note = [note, (event.quoted_image.caption if not arg.c else str())]
                note_type = bytes
            else:
                note = event.quoted_image
                note_type = Message
        elif event.quoted_msg:
            note = event.quoted_msg
            note_type = Message
        if note_type == Message and arg.c:
            note.caption = str()
        data = {
            args: {
                "user": user,
                "user_name": event.from_user.name,
                "note": note,
                "note_type": note_type,
            }
        }
        notes.update(data)
        await save2db2(bot.notes_dict, "note")
        await status_msg.edit(f"_Saved replied message to notes with name:_ *{args}*")
    except DownloadError:
        await status_msg.edit("*Download Failed!*\nPlease ask that it be resent.")
        await status_msg.react("ℹ️")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def get_notes(event, args, client):
    """
    Get saved notes;
    Arguments:
        None: Get all saved notes
        any: (note_name) Get a particular saved note*

    *Can also get notes through #note_name
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not args or (args and args.casefold() in ("all", "me", "notes", "my note")):
            return await list_notes(event, args, client)
        chat = event.chat.id
        chat_name = (
            (await bot.client.get_group_info(event.chat.jid)).GroupName.Name
            if event.chat.is_group
            else event.from_user.name
        )
        if not bot.notes_dict.get(chat):
            return await event.reply(f"_No notes found for chat:_ *{chat_name}*!")
        notes = bot.notes_dict[chat]
        if not (u_note := notes.get(args)):
            return await event.reply(
                f"Note with name: *{args}* not found in *{chat_name}*!"
            )
        user, note, note_type = (
            u_note.get("user"),
            u_note.get("note"),
            u_note.get("note_type"),
        )
        if note_type == str:
            msg = note  # + f"\n\nBy: @{user}"
            return await clean_reply(event, event.reply_to_message, "reply", msg)
        elif note_type == bytes:
            return await clean_reply(
                event,
                event.reply_to_message,
                "reply_photo",
                note[0],
                note[1],
                # (note[1] + f"\n\nBy: @{user}").lstrip("\n"),
            )
        elif note_type == Message:
            note = copy.deepcopy(note)
            newlines = "\n\n"
            # note.caption += f"{ newlines if note.caption else str()}By: @{user}"
            # note.contextInfo.mentionedJID.append(f"{user}@s.whatsapp.net")
            if hasattr(note, "viewOnce"):
                note.viewOnce = False
            return await clean_reply(
                event, event.reply_to_message, "reply", message=note
            )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def delete_notes(event, args, client):
    """
    Delete saved notes:
    Arguments:
        note_name: name of note to delete
        all: (Owner) delete all notes for this chat
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        chat = event.chat.id
        if event.chat.is_group:
            group_info = await bot.client.get_group_info(event.chat.jid)
            chat_name = group_info.GroupName.Name
            admin_user = user_is_admin(user, group_info.Participants)

        else:
            chat_name = "Pm"
            admin_user = False

        if not (notes := bot.notes_dict.get(chat)):
            return await event.reply(f"_No notes found for chat:_ *{chat_name}*!")
        if args.casefold() == "all":
            if not (user_is_owner(user) or admin_user) and event.chat.is_group:
                return await event.reply(f"*Permission denied.*")
            bot.notes_dict.pop(chat)
            await save2db2(bot.notes_dict, "note")
            return await event.reply(
                f"_Successfully removed all notes in_ *{chat_name}*"
            )
        if not (u_note := notes.get(args)):
            return await event.reply(
                f"Note with name: *{args}* not found in *{chat_name}!*"
            )
        if not (user_is_owner(user) or admin_user) and user != notes[args]["user"]:
            return await event.reply(
                "You can't delete this note; Most likely because *you* did not add it."
            )
        notes.pop(args)
        await save2db2(bot.notes_dict, "note")
        return await event.reply(f"_Successfully removed note with title:_ *{args}*")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def get_notes2(event, args, client):
    """
    Alias for get_notes
    """
    try:
        if event.type != "text":
            return
        if not event.text.startswith("#"):
            return
        if not event.text[1:]:
            return
        chat = event.chat.id
        if not (notes := bot.notes_dict.get(chat)):
            return
        if event.text[1:].casefold() == "notes":
            return await get_notes(event, None, None)
        if event.text[1:].casefold() == "my notes":
            return await list_notes(event, event.text[1:], None)
        if note := notes.get(event.text[1:]):
            return await get_notes(event, event.text[1:], None)
        await event.react("❓")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def tag_all_admins(event, args, client):
    """
    Tags all admins in a group
    """
    try:
        if event.type != "text":
            return
        acc_tup = ("@admin", "@mod")
        if not event.text.startswith(acc_tup):
            return
        if not event.chat.is_group:
            return await event.react("🚫")
        user = event.from_user.id
        if not user_is_privileged(user):
            if not chat_is_allowed(event):
                return
            if not user_is_allowed(user):
                return await event.react("⛔")
        group_info = await client.get_group_info(event.chat.jid)
        tags = tag_admins(group_info.Participants)
        await clean_reply(
            event,
            event.reply_to_message,
            "reply",
            tags if event.text.endswith("s") else tags.split()[0],
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def button(event, args, client):
    """ """
    try:
        message = event.message
        await client.send_message(
            message.Info.MessageSource.Chat,
            Message(
                viewOnceMessage=FutureProofMessage(
                    message=Message(
                        messageContextInfo=MessageContextInfo(
                            deviceListMetadata=DeviceListMetadata(),
                            deviceListMetadataVersion=2,
                        ),
                        interactiveMessage=InteractiveMessage(
                            body=InteractiveMessage.Body(text="Body Message"),
                            footer=InteractiveMessage.Footer(text="@krypton-byte"),
                            header=InteractiveMessage.Header(
                                title="Title Message",
                                subtitle="Subtitle Message",
                                hasMediaAttachment=False,
                            ),
                            nativeFlowMessage=InteractiveMessage.NativeFlowMessage(
                                buttons=[
                                    InteractiveMessage.NativeFlowMessage.NativeFlowButton(
                                        name="single_select",
                                        buttonParamsJSON='{"title":"List Buttons","sections":[{"title":"title","highlight_label":"label","rows":[{"header":"header","title":"title","description":"description","id":"select 1"},{"header":"header","title":"title","description":"description","id":"select 2"}]}]}',
                                    ),
                                    InteractiveMessage.NativeFlowMessage.NativeFlowButton(
                                        name="quick_reply",
                                        buttonParamsJSON='{"display_text":"Quick URL","url":"https://www.google.com","merchant_url":"https://www.google.com"}',
                                    ),
                                    InteractiveMessage.NativeFlowMessage.NativeFlowButton(
                                        name="cta_call",
                                        buttonParamsJSON='{"display_text":"Quick Call","id":"message"}',
                                    ),
                                    InteractiveMessage.NativeFlowMessage.NativeFlowButton(
                                        name="cta_copy",
                                        buttonParamsJSON='{"display_text":"Quick Copy","id":"123456789","copy_code":"message"}',
                                    ),
                                    InteractiveMessage.NativeFlowMessage.NativeFlowButton(
                                        name="cta_remainder",
                                        buttonParamsJSON='{"display_text":"Reminder","id":"message"}',
                                    ),
                                    InteractiveMessage.NativeFlowMessage.NativeFlowButton(
                                        name="cta_cancel_remainder",
                                        buttonParamsJSON='{"display_text":"Cancel Reminder","id":"message"}',
                                    ),
                                    InteractiveMessage.NativeFlowMessage.NativeFlowButton(
                                        name="address_message",
                                        buttonParamsJSON='{"display_text":"Address","id":"message"}',
                                    ),
                                    InteractiveMessage.NativeFlowMessage.NativeFlowButton(
                                        name="send_location", buttonParamsJSON=""
                                    ),
                                ]
                            ),
                        ),
                    )
                )
            ),
        )
    except Exception:
        await logger(Exception)
