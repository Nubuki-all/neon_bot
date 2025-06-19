import asyncio
import copy
import datetime
import io
import random
import uuid

import torch
from clean_links.clean import clean_url
from neonize.exc import DownloadError
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import Message
from PIL import Image
from RealESRGAN import RealESRGAN
from urlextract import URLExtract
from wand.image import Image as wand_image

from bot import Message
from bot.config import bot, conf
from bot.fun.quips import enquip, enquip4
from bot.fun.stickers import ran_stick
from bot.utils.bot_utils import (
    human_format_num,
    list_to_str,
    png_to_jpg,
    same_week,
    screenshot_page,
    split_text,
    sync_to_async,
    turn,
    wait_for_turn,
    waiting_for_turn,
)
from bot.utils.db_utils import save2db2
from bot.utils.log_utils import logger
from bot.utils.msg_store import get_deleted_message_ids, get_messages
from bot.utils.msg_utils import (
    chat_is_allowed,
    clean_reply,
    construct_msg_and_evt,
    find_role_mentions,
    function_dict,
    get_args,
    get_mentioned,
    get_user_info,
    tag_admins,
    tag_owners,
    tag_sudoers,
    tag_users,
    user_is_admin,
    user_is_allowed,
    user_is_owner,
    user_is_privileged,
)
from bot.utils.sudo_button_utils import create_sudo_button, wait_for_button_response


async def sticker_reply(event, args, client, overide=False):
    """
    Sends a random sticker upon being tagged
    """
    try:
        if not (event.text or event.caption):
            return
        bot.client.me = me = await bot.client.get_me()
        if not overide:
            # if not event.text.startswith("@"):
            # return
            if not "@" + (me.JID.User if not event.lid_address else me.LID.User) in (
                event.text or event.caption
            ):
                return
        reply = (
            event.reply_to_message
            if not event.caption and len(event.text.split()) == 1 and not overide
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
        quoted = event.reply_to_message
        if not (quoted or args):
            return await event.reply(f"{sanitize_url.__doc__}")
        status_msg = await event.reply("Please wait…")
        extractor = URLExtract()
        if quoted:
            msg = quoted.caption or quoted.text or ""
            urls = extractor.find_urls(msg)
            if not urls:
                return await event.reply(
                    f"*No link found in @{quoted.from_user.id}'s message to sanitize*"
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


async def screenshot(event, args, client):
    """
    Generate screenshots from all links in replied message

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
        quoted = event.reply_to_message
        if not (quoted or args):
            return await event.reply(f"{screenshot.__doc__}")
        status_msg = await event.reply("Please wait…")
        extractor = URLExtract()
        if quoted:
            msg = quoted.caption or quoted.text or ""
            urls = extractor.find_urls(msg)
            if not urls:
                return await event.reply(
                    f"*No link found in @{quoted.from_user.id}'s message*"
                )

        else:
            urls = extractor.find_urls(args)
            if not urls:
                return await event.reply(f"*No link found in your message*")
        for url in urls:
            try:
                image_url = await screenshot_page(url)
            except Exception:
                await logger(Exception)
                await event.reply(f"Screenshot generation failed for: {url}")
            else:
                await logger(e=image_url)
                await event.reply_photo(image_url, caption="Screenshot from webpage")
            await asyncio.sleep(3)
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
        Name of sticker [Optional]
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
                ["-nl", "store_false"],
                ["-c", "store_true"],
                ["-f", "store_true"],
                to_parse=args,
                get_unknown=True,
            )
            crop = arg.c
            forced = arg.f
            limit = arg.nl
        else:
            crop = False
            forced = False
            limit = True
        if not event.reply_to_message:
            return await event.reply("*Reply to a gif/image/video.*")
        if not (event.quoted_image or event.quoted_video):
            return await event.reply("*Replied message is not a gif/image/video.*")

        # forced = False if event.quoted_image else forced
        async with event.react("👩‍🏭"):
            file = await event.reply_to_message.download()
            bot.client.me = me = await bot.client.get_me()
            await event.send_typing_status()
            return await event.reply_sticker(
                file,
                quote=True,
                name=(args or random.choice((enquip(), enquip4()))),
                packname=me.PushName,
                crop=crop,
                enforce_not_broken=limit,
                animated_gif=forced,
            )
            await event.send_typing_status(False)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def sticker_to_image(event, args, client):
    "Converts replied sticker back to media"
    status_msg = None
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not event.reply_to_message:
            return await event.reply_sticker(
                "https://media1.tenor.com/m/DUHB3rClTaUAAAAd/no-pernalonga.gif",
                name="Reply to a sticker!",
                packname="Qiqi.",
            )
        if not event.reply_to_message.sticker:
            return await event.reply("Kindly reply to a sticker!")
        status_msg = await event.reply("Downloading sticker…")
        async with event.react("👩‍🏭"):
            file = await event.reply_to_message.download()
            if event.reply_to_message.sticker.isAnimated:
                await status_msg.edit("*Converting sticker to gif…*")
                with wand_image(blob=file, format="webp") as img:
                    with img.convert("gif") as img2:
                        gif = img2.make_blob(format="gif")
                await event.reply_gif(gif)
            else:
                await status_msg.edit("*Converting sticker to image…*")
                await event.reply_photo((await png_to_jpg(file)))
    except Exception:
        await logger(Exception)
        await event.react("❌")
    finally:
        if status_msg:
            await status_msg.delete()


async def undelete(event, args, client):
    """
    Undeletes a message;
    Argument:
      @mention : Specific user whose deleted messages should be retrieved; defaults to anyone
    Optional Parameter(s):
        -a : amount of deleted messages to fetch; defaults to 1 (one)
    """
    if not event.chat.is_group:
        return await event.react("🚫")
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        amount = None
        mentioned_ = False
        no_del_msg = True
        if args:
            arg, args = get_args(
                "-a",
                to_parse=args,
                get_unknown=True,
            )
            if arg.a and not arg.a.isdigit():
                await event.reply(f"-a: what is this? '{arg.a}'???")
                await asyncio.sleep(2)
            elif arg.a:
                amount = int(arg.a)
                if amount < 1:
                    await event.reply(f"-a: Sometimes i wonder…, reseting value…")
                    amount = None
        amount = 1 if not amount else amount
        mentioned = get_mentioned(args or "")
        # mentioned_ = bool(mentioned) slower?
        if mentioned:
            mentioned_ = True
        while mentioned:
            user_id = mentioned[0]
            try:
                del_ids = await get_deleted_message_ids(event.chat.id, amount, user_id)
                if not del_ids:
                    mentioned.pop(0)
                    continue
                status_msg = await event.reply(
                    f"Fetching {len(del_ids)} deleted message(s) for: @{user_id}"
                )
                await send_deleted_msgs(event, event.chat.id, del_ids, verbose=True)
                no_del_msg = False
                await status_msg.delete()
                mentioned.pop(0)
            except Exception:
                await logger(Exception)
                mentioned.pop(0)

        if not mentioned_:
            del_ids = await get_deleted_message_ids(event.chat.id, amount)
            if del_ids:
                await send_deleted_msgs(event, event.chat.id, del_ids)
                no_del_msg = False
        if no_del_msg:
            await event.reply("*No recently deleted messages found.*")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def send_deleted_msgs(event, chat_id, del_ids, verbose=False):
    msgs = await get_messages(chat_id, del_ids)
    if not msgs and verbose:
        sep = " ,"
        return await event.reply(
            f"*Could not find message(s) with ID(s):* '{list_to_str(del_ids, sep)}'"
        )
    elif not msgs:
        return await event.reply("*No recently deleted messages found.*")
    chain_reply = event
    for msg in msgs:
        if not hasattr(msg, "lid_address"):
            msg.lid_address = None
        await msg.reply(".")
        await asyncio.sleep(1)
        chain_reply = await chain_reply.reply(msg.media or msg.text)
        await asyncio.sleep(3)


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
        if not event.reply_to_message:
            return await event.reply(
                "*Command can only be used when replying to an image.*"
            )
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
        file = await event.reply_to_message.download()

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
            to_parse=(args or ""),
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
        msg_ = ""
        i = 1
        for title in list(notes.keys()):
            if filter_ and notes[title].get("user") != user:
                continue
            user_name = notes[title].get("user_name")
            msg_ += f"\n{i}. *{title}*{f' added by *{user_name}*' if event.chat.is_group and not filter_ else ''}"
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
        arg, args = get_args(
            ["-c", "store_true"],
            to_parse=args,
            get_unknown=True,
        )
        if not args:
            return await event.reply(f"{save_notes.__doc__}")
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
        status_msg = await event.reply("…")
        # note gen:
        note_type = str
        if event.quoted_text:
            note = event.quoted_text
        elif event.quoted_image:
            if event.quoted_image.fileLength < 5000000:
                note = await event.reply_to_message.download()
                note = [note, (event.quoted_image.caption if not arg.c else "")]
                note_type = bytes
            else:
                note = event.quoted_image
                note_type = Message
        elif event.quoted_msg:
            note = event.quoted_msg
            note_type = Message
        if note_type == Message and arg.c:
            note.caption = ""
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
        if not event.text:
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
        if not (text := (event.text or event.caption)):
            return
        if not event.chat.is_group:
            return
        if not (mentions := find_role_mentions(text, ["admin", "mod"])):
            return
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
            "_*Tagged all admins!*_" if mentions[0][1] else tags.split()[0],
            ghost_mentions=tags if mentions[0][1] else tags.split()[0],
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def tag_all_sudoers(event, args, client):
    """
    Tags all sudoers in a group
    """
    try:
        if not (text := (event.text or event.caption)):
            return
        if not event.chat.is_group:
            return
        if not (mentions := find_role_mentions(text, ["sudoer"])):
            return
        user = event.from_user.id
        # group_info = await client.get_group_info(event.chat.jid)
        if not user_is_privileged(user):
            if not chat_is_allowed(event):
                return
            if not user_is_allowed(user):
                return await event.react("⛔")
        tags = tag_sudoers()
        await clean_reply(
            event,
            event.reply_to_message,
            "reply",
            "_*Tagged all Sudoers!*_" if mentions[0][1] else tags.split()[0],
            ghost_mentions=tags if mentions[0][1] else tags.split()[0],
            mentions_are_jids=True,
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def tag_all_owners(event, args, client):
    """
    Tags all owners in a group
    """
    try:
        if not (text := (event.text or event.caption)):
            return
        if not event.chat.is_group:
            return
        if not (mentions := find_role_mentions(text, ["owner"])):
            return
        user = event.from_user.id
        # group_info = await client.get_group_info(event.chat.jid)
        if not user_is_privileged(user):
            if not chat_is_allowed(event):
                return
            if not user_is_allowed(user):
                return await event.react("⛔")
        tags = tag_owners()
        await clean_reply(
            event,
            event.reply_to_message,
            "reply",
            "_*Tagged all Owners!*_" if mentions[0][1] else tags.split()[0],
            ghost_mentions=tags if mentions[0][1] else tags.split()[0],
            mentions_are_jids=True,
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def tag_everyone(event, args, client):
    """
    Tags everyone in a group
    """
    try:
        if not (text := (event.text or event.caption)):
            return
        if not event.chat.is_group:
            return
        if not (mentions := find_role_mentions(text, ["all", "everyone"])):
            return
        user = event.from_user.id
        group_info = await client.get_group_info(event.chat.jid)
        if not user_is_privileged(user):
            if not user_is_admin(user, group_info.Participants):
                return
        tags = tag_users(group_info.Participants)
        await clean_reply(
            event,
            event.reply_to_message,
            "reply",
            "_*Tagged everyone!*_",
            ghost_mentions=tags,
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def rec_msg_ranking(event, args, client):
    """
    Helper for the message leaderboard
    """
    try:
        if not event.chat.is_group:
            return
        if not chat_is_allowed(event):
            return
        if not (event.is_revoke or event.text or event.caption or event.audio):
            return
        chat_id = event.chat.id
        msg_rank = bot.group_dict.setdefault(chat_id, {}).setdefault("msg_ranking", {})
        user = event.from_user.id
        if event.is_revoke:
            value = 0
            msgs = await get_messages(chat_id, event.revoked_id)
            if (
                msgs
                and msgs[0].from_user.id == event.from_user.id
                and (ts := msgs[0].message.Info.Timestamp)
            ):
                date = datetime.datetime.fromtimestamp(ts / 1000)
                if same_week(date, 0, 4):
                    value = -1
        else:
            value = 1
        msg_rank[user] = msg_rank.setdefault(user, 0) + value
        msg_rank["server"] = 0 if event.from_user.server == "lid" else 1
        msg_rank["total"] = msg_rank.setdefault("total", 0) + value
        bot.msg_leaderboard_counter += 1
    except Exception:
        await logger(Exception)


async def msg_ranking(event, args, client):
    """
    Get the Message Leaderboard of a particular group chat.
    Argument: -f/full (Get full ranking)
    """
    if not event.chat.is_group:
        return
    user = event.from_user.id
    if not (user_is_privileged(user)):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        chat_id = event.chat.id
        full = True if args and args in ("-f", "--full") else False
        msg = await get_ranking_msg(chat_id, full=full)
        if not msg:
            return await event.reply("Can't fetch ranking right now!")
        return await event.reply(msg, mentions_are_lids=True)
    except Exception:
        await logger(Exception)


async def get_ranking_msg(chat_id, tag=False, full=False):
    msg_rank_dict = bot.group_dict.setdefault(chat_id, {}).get(
        "msg_ranking", {"total": 0}
    )
    i = 1
    msg = ""
    server = msg_rank_dict.get("server")
    server = "lid" if not server else "s.whatsapp.net"
    sorted_ms_rank_dict = dict(
        sorted(msg_rank_dict.items(), key=lambda item: item[1], reverse=True),
    )

    for user in list(sorted_ms_rank_dict.keys()):
        if user in ("total", "server"):
            continue
        value = sorted_ms_rank_dict[user]
        user_info = await get_user_info(user, server)
        msg += f"{i}. {(user_info.PushName or '👤 Unknown') if not tag else ('@'+ user)} · {human_format_num(value)}\n"
        medals = get_medals(chat_id, user)
        msg += f"    └{medals}\n" if medals else ""
        i += 1
        if i > 10 and not full:
            break
    if not msg:
        return
    act_mem = len(msg_rank_dict.keys()) - 2
    total_msg = msg_rank_dict.get("total")
    return f"📈 *MESSAGE LEADERBOARD*\n{msg}\n👥 *Participants:* {human_format_num(act_mem)}\n✉️ *Total messages:* {human_format_num(total_msg)}"


def get_medals(chat_id, user):
    group = bot.group_dict.setdefault(chat_id, {})
    group.setdefault("msg_ranking")
    user_rank = group.get("msg_stats", {}).get(user, {})
    if not user_rank:
        return
    med_dict = {
        1: "🥇",
        2: "🥈",
        3: "🥉",
    }
    msg = ""
    for pos in list(user_rank):
        if not user_rank.get(pos):
            continue
        msg += f"{med_dict.get(pos)}: *{user_rank.get(pos)}*, "
    return msg.rstrip(", ")


async def gc_handler(gc_msg):
    try:
        leave = None
        if gc_msg.Leave:
            leave = True
        elif gc_msg.Join:
            pass
        else:
            return await logger(e=f"Unknown GroupInfoEv {gc_msg}")
        if not bot.group_dict.get(gc_msg.JID.User, {}).get("greetings"):
            return
        if leave:
            return await goodbye_msg(gc_msg)
        return await welcome_msg(gc_msg)
    except Exception:
        await logger(Exception)


async def goodbye_msg(gc_event):
    msg = "_It was nice knowing you, {}!_"
    user_info = await get_user_info(gc_event.Leave[0].User)
    await bot.client.send_message(
        gc_event.JID,
        msg.format(user_info.PushName or "@" + gc_event.Leave[0].User),
        mentions_are_lids=(gc_event.Leave[0].Server == "lid"),
    )


async def welcome_msg(gc_event):
    msg = "*Hi there* {0}, Welcome to *{1}*!\nRemember to be respectful and follow the rules."
    msg += "\n\n*Joined through:* {2}"
    # user_info = await get_user_info(gc_event.Join.User)
    group_info = await bot.client.get_group_info(gc_event.JID)
    chat_name = group_info.GroupName.Name
    user_name = f"@{gc_event.Join[0].User}"
    await bot.client.send_message(
        gc_event.JID,
        msg.format(user_name, chat_name, gc_event.JoinReason),
        mentions_are_lids=(gc_event.Join[0].Server == "lid"),
    )


async def save_filter(event, args, client):
    """
    Saves a replied Text/media message to bot database;
    Can be retrieved when a message content matches {filter_name}
    Argument:
        filter_name: name to save filter as & text to match in received messages
        -a: match any word
        -c: clean caption
        -m: match only words
    """
    chat = event.chat.id
    user = event.from_user.id
    if not event.chat.is_group:
        return
    if not user_is_privileged(user):
        group_info = await bot.client.get_group_info(event.chat.jid)
        if not user_is_admin(user, group_info.Participants):
            return
    try:
        arg, args = get_args(
            ["-a", "store_true"],
            ["-c", "store_true"],
            ["-m", "store_true"],
            to_parse=args,
            get_unknown=True,
        )
        if not (args and event.reply_to_message):
            return await event.reply(f"{save_filter.__doc__}")
        args = args.casefold()
        quoted = event.reply_to_message
        if not (event.quoted_msg or quoted.sticker or quoted.stickerPack):
            return await event.reply(
                "Can only save replied text or media as filter reply."
            )
        if args.casefold() in ("all", "notes", "my notes", "me") or len(args) < 3:
            return await event.reply(f"Given filter_name *{args}* is blocked.")
        if not user_is_owner(user) and args in function_dict:
            return await event.reply(f"Given filter_name *{args}* is blocked.")
        if (filters := bot.filters_dict.setdefault(chat, {})).get(args):
            if not user_is_owner(user) and user != filters[args]["user"]:
                return await event.reply(
                    f"Filter with name '{args}' already exists and can't be overwritten; Most likely because *you* did not add it."
                )
        status_msg = await event.reply("…")
        # filter gen:
        filter_type = str
        if event.quoted_text:
            new_filter = event.quoted_text
        elif event.quoted_image:
            if event.quoted_image.fileLength < 5000000:
                new_filter = await event.reply_to_message.download()
                new_filter = [
                    new_filter,
                    (event.quoted_image.caption if not arg.c else ""),
                ]
                filter_type = bytes
            else:
                new_filter = event.quoted_image
                filter_type = Message
        elif new_filter := event.quoted_msg or quoted.sticker:
            filter_type = Message
        elif new_filter := quoted.stickerPack:
            filter_type = Message
            if not new_filter.publisher:
                new_filter.publisher = bot.client.me.PushName
        if filter_type == Message and arg.c and hasattr(new_filter, "caption"):
            new_filter.caption = ""
        data = {
            args: {
                "user": user,
                "user_name": event.from_user.name,
                "filter": new_filter,
                "filter_type": filter_type,
                "match_any": arg.a,
                "match_word": arg.m,
            }
        }
        filters.update(data)
        await save2db2(bot.filters_dict, "filter")
        await status_msg.edit(f"_Saved replied message to filters with name:_ *{args}*")
    except DownloadError:
        await status_msg.edit("*Download Failed!*\nPlease ask that it be resent.")
        await status_msg.react("ℹ️")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def list_filters(event, args, client):
    """
    Fetches the list of filters in a chat:
    Arguments: [None]
    """
    user = event.from_user.id
    if not event.chat.is_group:
        return
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        chat = event.chat.id
        chat_name = (await bot.client.get_group_info(event.chat.jid)).GroupName.Name
        if not (filters := bot.filters_dict.get(chat)):
            return await event.reply(f"*No filters found for chat: {chat_name}!*")
        reply = await event.reply("_Fetching filters…_")
        filter_ = True if args and args.casefold() in ("my filters", "me") else False
        msg = f"*{'Your l' if filter_ else 'L'}ist of filters in {chat_name}*"
        msg_ = ""
        i = 1
        for title in list(filters.keys()):
            if filter_ and filters[title].get("user") != user:
                continue
            user_name = filters[title].get("user_name")
            msg_ += (
                f"\n{i}. *{title}*{f' added by *{user_name}*' if not filter_ else ''}"
            )
            i += 1
        if not msg_:
            return await event.reply(
                f"*You currently have no saved filters in {chat_name}*!"
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


async def delete_filters(event, args, client):
    """
    Delete saved filters:
    Arguments:
        filter_name: name of filter to delete
        all: (Owner) delete all filters for this chat
    """
    user = event.from_user.id
    if not event.chat.is_group:
        return
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        chat = event.chat.id
        group_info = await bot.client.get_group_info(event.chat.jid)
        admin_user = user_is_admin(user, group_info.Participants)
        chat_name = group_info.GroupName.Name

        if not (filters := bot.filters_dict.get(chat)):
            return await event.reply(f"_No filters found for chat:_ *{chat_name}*!")
        args = args.casefold()
        if args == "all":
            if not (user_is_owner(user) or admin_user):
                return await event.reply(f"*Permission denied.*")
            bot.filters_dict.pop(chat)
            await save2db2(bot.filters_dict, "filter")
            return await event.reply(
                f"_Successfully removed all filters in_ *{chat_name}*"
            )
        if not (svd_filter := filters.get(args)):
            return await event.reply(
                f"Filter with name: *{args}* not found in *{chat_name}!*"
            )
        if not (user_is_owner(user) or admin_user) and user != svd_filter["user"]:
            return await event.reply(
                "You can't delete this filter; Most likely because *you* did not add it."
            )
        filters.pop(args)
        await save2db2(bot.filters_dict, "filter")
        return await event.reply(f"_Successfully removed filter with title:_ *{args}*")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def detect_filters(event, args, client):
    """
    Get saved filters;
    AUTO FUNCTION
    """
    user = event.from_user.id
    if not event.chat.is_group:
        return
    if not chat_is_allowed(event):
        return
    if bot.client.me and bot.client.me.JID.User == user:
        return
    if not (event.caption or event.text):
        return
    try:
        chat = event.chat.id
        if not (filters := bot.filters_dict.get(chat)):
            return
        cmd_pre = conf.CMD_PREFIX
        msg = event.caption or event.text
        msg = msg.casefold()
        if msg.startswith((f"{cmd_pre}filter", f"{cmd_pre}del_filter")):
            return
        match_list = [*filters]
        matches = [m for m in match_list if m in msg]
        filtered = 0
        await asyncio.sleep(2)
        for match in matches:
            result = await get_filters(event, match, client)
            if result:
                filtered += 1
                await asyncio.sleep(2)
            if filtered >= 2:
                break
    except Exception:
        await logger(Exception)
        # await event.react("❌")


async def get_filters(event, args, client):
    chat = event.chat.id
    if not (filters := bot.filters_dict.get(chat)):
        return
    # Tab to edit
    if not (svd_filter := filters.get(args)):
        return
    if svd_filter.get("match_any"):
        msg = event.caption or event.text
        if not set(args.split()) <= set(msg.casefold().split()):
            return
    if svd_filter.get("match_word"):
        msg = event.caption or event.text
        if not f" {args} " in f" {msg.casefold()} ":
            return
    user, filter_data, filter_type = (
        svd_filter.get("user"),
        svd_filter.get("filter"),
        svd_filter.get("filter_type"),
    )
    if filter_type == str:
        msg = filter_data  # + f"\n\nBy: @{user}"
        return await event.reply(msg)
    elif filter_type == bytes:
        return await event.reply_photo(
            filter_data[0],
            filter_data[1],
            # (note[1] + f"\n\nBy: @{user}").lstrip("\n"),
        )
    elif filter_type == Message:
        filter_data = copy.deepcopy(filter_data)
        newlines = "\n\n"
        # note.caption += f"{ newlines if note.caption else str()}By: @{user}"
        # note.contextInfo.mentionedJID.append(f"{user}@s.whatsapp.net")
        if hasattr(filter_data, "viewOnce"):
            filter_data.viewOnce = False
        return await event.reply(message=filter_data)


async def test_button(event, args, client):
    user = event.from_user.id
    if not (user_is_privileged(user)):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        button_dict = {}
        button_dict.update({uuid.uuid4(): ["Button 1", "Some information."]})
        button_dict.update({uuid.uuid4(): ["Button 2", "Another information."]})
        button_dict.update({uuid.uuid4(): ["Button 3", "More information."]})
        title = "Poll message to test the usability of polls as buttons."
        poll_msg_, msg_id = await create_sudo_button(
            title, button_dict, event.chat.jid, user
        )
        poll_msg = construct_msg_and_evt(
            event.chat.id,
            bot.client.me.JID.User,
            msg_id,
            None,
            event.chat.server,
            bot.client.me.JID.Server,
            poll_msg_,
        )
        if not (results := await wait_for_button_response(msg_id)):
            await event.reply("yikes.")
        await poll_msg.delete()
        info = button_dict.get(results[0])
        await event.reply(f"{info[0]} was pressed.\n*Value:* {info[1]}")
    except Exception:
        await logger(Exception)


# Add command handlers
bot.add_handler(get_notes2)
bot.add_handler(tag_everyone)
bot.add_handler(detect_filters)
bot.add_handler(tag_all_admins)
bot.add_handler(tag_all_owners)
bot.add_handler(tag_all_sudoers)
bot.add_handler(rec_msg_ranking)

bot.add_handler(get_notes, "get")
bot.add_handler(undelete, "undel")
bot.add_handler(pick_random, "random")
bot.add_handler(list_filters, "filters")
bot.add_handler(sanitize_url, "sanitize")
bot.add_handler(screenshot, "screenshot")
bot.add_handler(upscale_image, "upscale")
bot.add_handler(msg_ranking, "msg_ranking")
bot.add_handler(stickerize_image, "sticker")
bot.add_handler(sticker_to_image, "stick2img")

bot.add_handler(
    save_notes,
    "save",
    require_args=True,
)
bot.add_handler(
    save_filter,
    "filter",
    require_args=True,
)
bot.add_handler(
    delete_notes,
    "del_note",
    require_args=True,
)
bot.add_handler(
    delete_filters,
    "del_filter",
    require_args=True,
)


# test
bot.add_handler(test_button, "button")
