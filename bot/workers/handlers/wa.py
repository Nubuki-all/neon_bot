import asyncio
import copy
import datetime
import io
import random
import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime as dt
from os.path import splitext as split_ext

import torch
from clean_links.clean import clean_url
from neonize.exc import DownloadError
from neonize.utils.enum import MediaType
from neonize.utils.ffmpeg import AFFmpeg
from neonize.utils.jid import Jid2String
from PIL import Image
from RealESRGAN import RealESRGAN
from urlextract import URLExtract
from wand.image import Image as wand_image

from bot import Message
from bot.config import bot, conf
from bot.fun.quips import enquip, enquip4
from bot.fun.stickers import ran_stick
from bot.others.exceptions import StopAutoHandlers, StopHandlers
from bot.pkgs.tikmate_dl import TikmateAsync
from bot.utils.bot_utils import (
    LimitedDict,
    get_date_from_isostr,
    get_fps,
    get_mediainfo,
    human_format_num,
    image_to_png,
    is_video_file,
    list_to_str,
    png_to_jpg,
    post_to_tgph,
    read_binary,
    same_week,
    screenshot_page,
    split_text,
    sync_to_async,
    turn,
    upscaled_png_to_jpg,
    video_timestamp_to_seconds,
    wait_for_turn,
    waiting_for_turn,
    write_binary,
)
from bot.utils.db_utils import save2db2
from bot.utils.events import SEQUENTIAL_AUTO, Event
from bot.utils.log_utils import log, logger
from bot.utils.modal_utils import upscale_batch
from bot.utils.msg_store import (
    get_deleted_message_ids,
    get_messages,
    get_messages_between,
    get_messages_by_album_id,
)
from bot.utils.msg_utils import (
    chat_is_allowed,
    clean_reply,
    construct_msg_and_evt,
    dd_media,
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
from bot.utils.os_utils import enshell, s_remove, size_of
from bot.utils.parse_td_utils import parse_reminder_time_hybrid
from bot.utils.sudo_button_utils import create_sudo_button, wait_for_button_response
from bot.utils.ytdl_utils import is_valid_trim_args, trim_vid
from bot.workers.auto.reminder import cancel_reminder, schedule_reminder_async

Image.MAX_IMAGE_PIXELS = 400_000_000

compress_cache = LimitedDict()
sanitized_video_cache = LimitedDict()
mediainfo_cache = LimitedDict()
purge_sessions = {}


async def tools(event, args, client):
    """Show the list of available tools/commands."""
    try:
        pre = conf.CMD_PREFIX
        s = "\n"
        msg = (
            f"*Filters:*{s}"
            f"{pre}del_filter - *Delete a filter, or all filters*{s}"
            f"{pre}filter - *[Owner | Sudo | Admin] Reply with the replied message when a word is sent*{s}"
            f"{pre}filters - *List the group's filters*{s}"
            f"{s}"
            f"*Notes:*{s}"
            f"{pre}del_note - *Delete a saved note, or all notes*{s}"
            f"{pre}get - *Get a saved note or list all notes*{s}"
            f"{pre}save - *Save a replied text/media as a note*{s}"
            f"{s}"
            f"*Videos & Images*{s}"
            f"{pre}compress - *Compress a replied video (AV1/HEVC)*{s}"
            f"{pre}doc - *Convert a replied video/image/sticker to a document*{s}"
            f"{pre}fps - *Get the fps of a replied video/gif*{s}"
            f"{pre}mediainfo - *Get the mediainfo of a replied video/gif*{s}"
            f"{pre}mp3 - *Convert a replied video to mp3, optionally trimmed*{s}"
            f"{pre}sanitize_video - *Re-encode a replied video that won't play*{s}"
            f"{pre}tikmate - *Download TikTok videos/images*{s}"
            f"{pre}upscale - {'*Upscale replied image*' if not bot.disable_cic else '_Currently not available!_'}{s}"
            f"{pre}batch_upscale - {'*Upscale replied album images*' if conf.MODAL_UPSCALE_API else '_Currently not available!_'}{s}"
            f"{s}"
            f"{pre}msg_ranking - *Get the group's message leaderboard*{s}"
            f"{pre}pin - *[Owner | Sudo | Admin] Pin a replied message*{s}"
            f"{pre}unpin - *[Owner | Sudo | Admin] Unpin a replied message*{s}"
            f"{pre}purge - *[Owner | Admin] Mass delete messages*{s}"
            f"{pre}random - *Pick random item(s) from a replied list*{s}"
            f"{pre}repeat - *Repeat a replied message*{s}"
            f"{pre}sanitize - *Remove tracking from links in a message*{s}"
            f"{pre}screenshot - *Screenshot webpage(s) from link(s)*{s}"
            f"{s}"
            f"*Reminders:*{s}"
            f"{pre}remindme - *Get reminded of a (replied) message at a set time*{s}"
            f"{pre}all_reminders - *List your reminders in this chat*{s}"
            f"{pre}del_reminder - *Delete one or all of your reminders*{s}"
            f"{s}"
            f"*Greetings:*{s}"
            f"{pre}greetings - *[Owner | Sudo | Admin] Enable/Disable greetings in group chats*{s}"
            f"{pre}setwelcome - *[Admins Only] Set a custom welcome message*{s}"
            f"{pre}unsetwelcome - *[Admins Only] Unset the custom welcome message*{s}"
            f"{s}"
            f"*Rules:*{s}"
            f"{pre}rules - *Get group rules in PM/DM*{s}"
            f"{pre}setrules - *[Admins Only] Set group rules*{s}"
            f"{pre}delrules - *[Admins Only] Delete group rules*{s}"
            f"{s}"
            f"*Stickers:*{s}"
            f"{pre}kang - *Kang a replied sticker*{s}"
            f"{pre}sticker - *Turn images/videos/gifs/albums into stickers*{s}"
            f"{pre}stick2img - *Turn a sticker into an image/gif*{s}"
            f"{s}"
            f"{pre}undel - *Resend recently deleted messages*{s}"
        )
        await event.reply(msg)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def to_doc(event, args, client):
    """
    Convert a replied image, video or sticker to a document.
    Must be used as a reply; the original caption is kept.
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not (replied := event.reply_to_message):
            return await event.reply("*Kindly reply to a video/image/sticker.*")
        if replied.document:
            return await event.reply("*Replied message is a document.*")
        ext = ""
        if replied.video:
            ext = "mp4"
        elif replied.image:
            ext = replied.image.mimetype.split("/")[1]
        elif replied.sticker:
            ext = "webp"
        else:
            return await event.reply("*Replied message is not a video/image/sticker.*")

        async with event.react("📥"):
            file = await replied.download()
        file_name = (
            f"{replied.short_name}_" + dt.now().isoformat("_", "seconds") + f".{ext}"
        )
        async with event.react("📤"):
            await event.reply_document(file, file_name, replied.caption)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def sanitize_video(event: Event, args: str, client):
    """
    Re-encode a replied video (or video document) so it plays again.
    Fixes the "The video is not available because something is wrong
    with the video file" error.
    Videos over 100MB are sent back as documents.
    Arguments: None
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not (replied := event.reply_to_message):
            return await event.reply("*Kindly reply to video.*")
        f_name = ""
        ext = ".mp4"
        if replied.document:
            if not (
                replied.document.mimetype.startswith("video")
                or is_video_file(replied.document.fileName)
            ):
                return await event.reply("*Replied document is not a video.*")
            f_name, ext = split_ext(replied.document.fileName)
        elif not replied.video:
            return await event.reply("*Replied message is not a video.*")
        comp_sha = replied.media.fileSHA256
        if media := sanitized_video_cache.get(comp_sha):
            try:
                async with event.react("📥"):
                    file = await dd_media(media, MediaType.MediaDocument)
                async with event.react("📤"):
                    file_name = f_name or "video_" + dt.now().isoformat("_", "seconds")
                    file_name += ".mp4"
                    if len(file) > 100000000:
                        e = await event.reply_document(file, file_name, file_name)
                    else:
                        e = await event.reply_video(file, file_name)
                sanitized_video_cache[comp_sha] = e.media
                return
            except Exception:
                await logger(Exception)
                sanitized_video_cache.pop(comp_sha)
        async with event.react("📥"):
            file = await replied.download()

        _id = f"{event.chat.id}:{event.id}"
        in_ = f"temp/{_id}{ext}"
        out_ = f"temp/{_id}-1.mp4"
        cmd_str = f"ffmpeg -fflags +genpts+igndts -err_detect ignore_err -max_error_rate 1.0 -i {in_} -map 0:v -map 0:a? -c:v libx264 -c:a copy -movflags +faststart {out_} -y"

        await write_binary(in_, file)

        async with event.react("⏲️"), comp_sem:
            process, _stdout, stderr = await enshell(cmd_str)
        if process.returncode != 0:
            raise RuntimeError(
                # type: ignore
                f"stderr: {stderr} Return code: {process.returncode}"
            )
        s_remove(in_)
        async with event.react("📤"):
            file_name = f_name or "video_" + dt.now().isoformat("_", "seconds")
            file_name += ".mp4"
            file_sz = size_of(out_)
            if file_sz > 2 << 30:
                s_remove(out_)
                return await event.reply("*Upload failed, Video is too large!*")
            if file_sz > 100000000:
                e = await event.reply_document(out_, file_name, file_name)
            else:
                e = await event.reply_video(out_, f_name)
            sanitized_video_cache[comp_sha] = e.media
        s_remove(out_)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def to_mp3(event, args, client):
    """
    Convert a replied video (or video document) to mp3.
    Arguments:
        -s: start time to trim from (default: start)
        -t: end time to trim to (default: end)
    Invalid trim times are ignored and the full audio is sent.
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not (replied := event.reply_to_message):
            return await event.reply("*Kindly reply to video.*")
        if replied.document:
            if not (
                replied.document.mimetype.startswith("video")
                or is_video_file(replied.document.fileName)
            ):
                return await event.reply("*Replied document is not a video.*")
        elif not replied.video:
            return await event.reply("*Replied message is not a video.*")

        arg, args = get_args(
            "-s",
            "-t",
            to_parse=(args or ""),
            get_unknown=True,
        )
        trim_args = None
        async with event.react("📥"):
            file = await replied.download()

        async with event.react("💿"):
            async with AFFmpeg(file) as ffmpeg:
                duration = int((await ffmpeg.extract_info()).format.duration)
                audio = await ffmpeg.to_mp3()
            if arg.s or arg.t:
                if not (arg.t and arg.s):
                    arg.s = arg.s or "0"
                    arg.t = arg.t or str(duration)
                trim_args = arg.s + "-" + arg.t
                if not is_valid_trim_args(trim_args, total_dur=duration):
                    trim_args = None

        if trim_args:
            _id = f"{event.chat.id}:{event.id}"
            st_, et_ = map(video_timestamp_to_seconds, trim_args.split("-"))
            in_ = f"trim/{_id}.mp3"
            out_ = f"trim/{_id}-1.mp3"
            async with event.react("✂️"):
                await write_binary(in_, audio)
                await trim_vid(st_, et_, in_, out_)
                s_remove(in_)
                audio = await read_binary(out_)
                s_remove(out_)

        async with event.react("📤"):
            await event.reply_audio(audio)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def getfps(event, args, client):
    "Get the fps of a replied video, video/gif document or animated sticker."
    return await vinfo(event, "fps", client)


async def getminfo(event, args, client):
    """
    Get the mediainfo of a replied video, video/gif document or animated sticker.
    Sent as a Telegraph link by default.
    Arguments:
        -f: send the full mediainfo as a text document instead
    """
    if args == "-f":
        return await vinfo(event, "media_info", client)
    return await vinfo(event, "media_info_link", client)


async def vinfo(event: Event, args: str, client):
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not (replied := event.reply_to_message):
            return await event.reply("*Kindly reply to video.*")
        ext = ".mp4"
        if replied.document:
            mimetype = replied.document.mimetype
            if not (
                mimetype.startswith("video")
                or mimetype == "image/gif"
                or is_video_file(replied.document.fileName)
            ):
                return await event.reply("*Replied message is not a video.*")
            _, ext = split_ext(replied.document.fileName)
        elif replied.sticker:
            if not replied.sticker.isAnimated:
                return await event.reply("*Replied message is not an animated sticker*")
            ext = ".webp"
        elif not replied.video:
            return await event.reply("*Replied message is not a video.*")
        args = args or ""

        @dataclass
        class VideoInfo:
            media_info: str = ""
            media_info_link: str = ""
            fps: float = 0.0

        async def _send(info: VideoInfo) -> bool:
            match args.casefold():
                case "fps":
                    await event.reply(f"FPS: {info.fps}")
                case "media_info":
                    await event.reply_document(
                        info.media_info.encode("utf-8"), "mediainfo.txt", "mediainfo"
                    )
                case "media_info_link":
                    await event.reply(f"*Mediainfo:* {info.media_info_link}")
                case _:
                    return False
            return True

        async def _process(info: VideoInfo) -> bool:
            if (
                args == "fps"
                and info.fps
                or args == "media_info"
                and info.media_info
                or args == "media_info_link"
                and info.media_info_link
            ):
                return await _send(info)
            else:
                return False

        comp_sha = replied.media.fileSHA256
        info = mediainfo_cache.get(comp_sha)
        if info:
            if await _process(info):
                return
        else:
            info = VideoInfo()
        _id = f"{event.chat.id}:{event.id}"
        fn = f"comp/{_id}{ext}"
        async with event.react("📥"):
            file = await replied.download()
        await write_binary(fn, file)

        async def _populate(i: VideoInfo):
            if not i.fps:
                try:
                    i.fps = round(float(await get_fps(fn)), 2)
                except Exception:
                    await logger(Exception)
            if not i.media_info:
                try:
                    i.media_info = await get_mediainfo(fn, full=True)
                except Exception:
                    await logger(Exception)
            if not i.media_info_link:
                try:
                    content = await get_mediainfo(fn, html=True)
                    if len(content) > 65536:
                        content = (
                            content[:65430]
                            + "<strong>...<strong><br><br><strong>(TRUNCATED DUE TO CONTENT EXCEEDING MAX LENGTH)<strong>"
                        )
                    i.media_info_link = (
                        await post_to_tgph(
                            "Mediainfo", content, bot.client.me.PushName, ""
                        )
                    )["url"]
                except Exception:
                    await logger(Exception)

        await _populate(info)
        mediainfo_cache[comp_sha] = info
        if await _process(info):
            return
        await event.react("😖")
    except Exception:
        await logger(Exception)
        await event.react("❌")


comp_sem = asyncio.Semaphore(4)


async def compress(event, args, client):
    """
    Compress a replied video (or video document).
    Returns an AV1 (or HEVC) mkv as a document.
    Arguments:
        480p (default), 720p or 1080p: output resolution
        --hevc: encode with HEVC (x265) instead of AV1
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not (replied := event.reply_to_message):
            return await event.reply("*Kindly reply to video.*")
        ext = ""
        f_name = ""
        if replied.document:
            if not (
                replied.document.mimetype.startswith("video")
                or is_video_file(replied.document.fileName)
            ):
                return await event.reply("*Replied message is not a video.*")
            f_name, ext = split_ext(replied.document.fileName)
        elif not replied.video:
            return await event.reply("*Replied message is not a video.*")
        hevc = False
        if args and "--hevc" in args:
            args = args.replace("--hevc", "").strip()
            hevc = True
        args = args.casefold() if args else ""
        if args not in ["480p", "720p", "1080p"]:
            args = ""
        ext = ext or ".mp4"
        comp_sha = (
            replied.media.fileSHA256 + args.encode("utf-8")
            if args
            else replied.media.fileSHA256
        ) + (b"--hevc" if hevc else b"")
        if media := compress_cache.get(comp_sha):
            try:
                async with event.react("📥"):
                    file = await dd_media(media, MediaType.MediaDocument)
                async with event.react("📤"):
                    file_name = f_name or "video_" + dt.now().isoformat("_", "seconds")
                    file_name += ".mkv"
                    e = await event.reply_document(file, file_name, file_name)
                compress_cache[comp_sha] = e.media
                return
            except Exception:
                await logger(Exception)
                compress_cache.pop(comp_sha)

        async with event.react("📥"):
            file = await replied.download()

        _id = f"{event.chat.id}:{event.id}"
        in_ = f"comp/{_id}{ext}"
        out_ = f"comp/{_id}-1.mkv"
        a_quality = {"480p": "32k", "720p": "64k", "1080p": "128k"}
        crf_quality = {"1080p": "35"}
        title_ = (replied.caption or "").split("\n")[-1]
        video_codec = "libx265" if hevc else "libsvtav1"
        video_params = (
            "-crf 30"
            if hevc
            else f'-preset 9 -g 240 -svtav1-params tune=1:film-grain=0 -crf {crf_quality.get(args, "42")}'
        )

        quality = {
            "480p": 480,
            "720p": 720,
            "1080p": 1080,
        }

        height = quality.get(args, 480)

        cmd_str = f'''ffmpeg -i "{in_}" \
        -map 0:v? -map 0:a? -map 0:s? -map 0:t? \
        -metadata title="{title_} | MiNi" \
        -c:v {video_codec} \
        {video_params} \
        -vf "scale='if(gt(iw,ih),-2,{height})':'if(gt(iw,ih),{height},-2)'" \
        -pix_fmt yuv420p \
        -c:a libopus -ac 2 -vbr 2 -ab {a_quality.get(args, "32k")} \
        -c:s copy \
        "{out_}"'''
        await write_binary(in_, file)

        async with event.react("⏲️"), comp_sem:
            process, _stdout, stderr = await enshell(cmd_str)
        if process.returncode != 0:
            raise RuntimeError(
                # type: ignore
                f"stderr: {stderr} Return code: {process.returncode}"
            )
        s_remove(in_)
        async with event.react("📤"):
            file_name = f_name or "video_" + dt.now().isoformat("_", "seconds")
            file_name += ".mkv"
            e = await event.reply_document(out_, file_name, file_name)
            compress_cache[comp_sha] = e.media
        s_remove(out_)
    except Exception:
        await logger(Exception)
        await event.react("❌")


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
    Remove tracking parameters from all links in a replied message
    and resend the message with the cleaned links.

    Usage:
        Reply to a message, or pass link(s) as the argument.
    """
    status_msg = None
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        replied = event.reply_to_message
        if not (replied or args):
            return await event.reply(f"{sanitize_url.__doc__}")
        status_msg = await event.reply("Please wait…")
        extractor = URLExtract()
        if replied and not args:
            msg = replied.caption or replied.text or ""
            urls = extractor.find_urls(msg)
            if not urls:
                return await event.reply(
                    f"*No link found in @{replied.from_user.id}'s message to sanitize*"
                )
            new_msg = msg
            sanitized_links = []
            for url in urls:
                sanitized_links.append(clean_url(url))
            for a, b in zip(urls, sanitized_links):
                new_msg = new_msg.replace(a, b)
            return await clean_reply(event, replied, "reply", new_msg)
        urls = extractor.find_urls(args)
        if not urls:
            return await event.reply("*No link found in your message to sanitize*")
        msg = "*Sanitized link(s):*"
        for url in urls:
            msg += f"\n\n{clean_url(url)}"
        return await clean_reply(event, replied, "reply", msg)
    except Exception:
        await logger(Exception)
        await event.react("❌")
    finally:
        if status_msg:
            await status_msg.delete()


async def screenshot(event, args, client):
    """
    Screenshot every link in a replied message.
    Without a reply, screenshots the link(s) given as argument.
    Arguments:
      -l: low quality image
      -d: disable dark mode (dark mode is on by default)
      -f: full-page (scrolling) screenshot
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        replied = event.reply_to_message
        if not (replied or args):
            return await event.reply(f"{screenshot.__doc__}")
        await event.react("🌐")
        extractor = URLExtract()
        if replied:
            msg = replied.caption or replied.text or ""
            urls = extractor.find_urls(msg)
            if not urls:
                return await event.reply(
                    f"*No link found in @{replied.from_user.id}'s message*"
                )

        else:
            urls = extractor.find_urls(args)
            if not urls:
                return await event.reply("*No link found in your message*")
        arg, args = get_args(
            ["-l", "store_true"],
            ["-d", "store_false"],
            ["-f", "store_true"],
            to_parse=args or "",
            get_unknown=True,
        )
        for url in urls:
            try:
                image = await screenshot_page(url, arg.f, arg.d, arg.l)
            except Exception:
                await logger(Exception)
                await event.reply(f"Screenshot generation failed for: {url}")
            else:
                await event.reply_photo(image, caption="Screenshot from webpage")
            await asyncio.sleep(3)
    except Exception:
        await logger(Exception)
        await event.react("❌")
    finally:
        await event.react("")


async def kang_sticker(event, args, client):
    """
    Kang a replied sticker (resend it under the bot's pack name).
    Arguments:
        name: sticker name [Optional]; random if not given
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not (replied := event.reply_to_message):
            return await event.reply("*Reply to a sticker to kang.*")
        if not replied.sticker:
            return await event.reply("*Replied message is not a sticker.*")

        async with event.react("📥"):
            file = await replied.download()

        async with event.react("👩‍🏭"):
            bot.client.me = me = await bot.client.get_me()
            return await event.reply_sticker(
                file,
                quote=True,
                name=(args or random.choice((enquip(), enquip4()))),
                packname=me.PushName,
                passthrough=True,
            )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def stickerize_image(event: Event, args: str, client):
    """
    Turn a replied image/gif/video (or image/video document) into a sticker.
    Replying to an album makes a sticker pack instead.
    Arguments:
        name: sticker (or pack) name [Optional]; random if not given
        -q: quality (1-100), default 75
        -cl: compression level (1-6), default 4
        -c: crop
        -f: force animated gif mode
        -nl: skip the not-broken check (single stickers only)
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        args_ = args
        quality = 75
        compression_level = 4
        if args:
            arg, args = get_args(
                "-q",
                "-cl",
                ["-nl", "store_false"],
                ["-c", "store_true"],
                ["-f", "store_true"],
                to_parse=args,
                get_unknown=True,
            )
            crop = arg.c
            forced = arg.f
            limit = arg.nl
            if q := arg.q:
                if not q.isdigit():
                    await event.reply(f"-q: argument requires a digit not {q}")
                else:
                    quality = int(q)
            if cl := arg.cl:
                if not cl.isdigit():
                    await event.reply(f"-cl: argument requires a digit not {cl}")
                else:
                    compression_level = int(cl)
        else:
            crop = False
            forced = False
            limit = True
        if not (replied := event.reply_to_message):
            return await event.reply("*Reply to a gif/image/video/album.*")
        if replied.short_name == "album":
            return await stickerize_album(event, args_, client)
        if not (replied.image or replied.video):
            # Check if there's no document, or the document isn't an
            # image/video
            if not replied.document or not (
                replied.document.mimetype.startswith("video")
                or replied.document.mimetype.startswith("image")
            ):
                return await event.reply("*Replied message is not a gif/image/video.*")

        async with event.react("📥"):
            file = await replied.download()

        async with event.react("👩‍🏭"):
            bot.client.me = me = await bot.client.get_me()
            return await event.reply_sticker(
                file,
                quote=True,
                name=(args or random.choice((enquip(), enquip4()))),
                packname=me.PushName,
                crop=crop,
                enforce_not_broken=limit,
                animated_gif=forced,
                quality=quality,
                compression_level=compression_level,
            )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def stickerize_album(event: Event, args: str, client):
    """
    Turn a replied album into a sticker pack.
    Arguments:
        name: pack name [Optional]; random if not given
        -q: quality (1-100), default 75
        -cl: compression level (1-6), default 4
        -c: crop
        -f: force animated gif mode
    """
    try:
        quality = 75
        compression_level = 4
        if args:
            arg, args = get_args(
                "-q",
                "-cl",
                ["-nl", "store_false"],  # single stickers only; ignored here
                ["-c", "store_true"],
                ["-f", "store_true"],
                to_parse=args,
                get_unknown=True,
            )
            crop = arg.c
            forced = arg.f
            if q := arg.q:
                if not q.isdigit():
                    await event.reply(f"-q: argument requires a digit not {q}")
                else:
                    quality = int(q)
            if cl := arg.cl:
                if not cl.isdigit():
                    await event.reply(f"-cl: argument requires a digit not {cl}")
                else:
                    compression_level = int(cl)
        else:
            crop = False
            forced = False
        replied = event.reply_to_message
        async with event.react("🗂️"):
            medias = await get_messages_by_album_id(event.chat.id, replied.id)
        if not medias:
            return await event.reply("*Replied album media(s) could not be retrieved.*")
        funcs = [media.download() for media in medias]
        async with event.react("📥"):
            files = await asyncio.gather(*funcs)

        async with event.react("👩🏻‍🏭"):
            bot.client.me = me = await bot.client.get_me()
            return await event.reply_stickerpack(
                files,
                quote=True,
                packname=(args or random.choice((enquip(), enquip4()))),
                publisher=me.PushName,
                crop=crop,
                animated_gif=forced,
                quality=quality,
                compression_level=compression_level,
            )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def sticker_to_image(event, args, client):
    "Convert a replied sticker to an image (png), or a gif if animated."
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
                packname="N.",
            )
        if not event.reply_to_message.sticker:
            return await event.reply("Kindly reply to a sticker!")
        is_animated = False
        async with event.react("📥"):
            file = await event.reply_to_message.download()
        async with event.react("👩‍🏭"):
            if event.reply_to_message.sticker.isAnimated:
                is_animated = True
                with wand_image(blob=file, format="webp") as img:
                    with img.convert("gif") as img2:
                        img2.coalesce()
                        gif = img2.make_blob(format="gif")
            else:
                with wand_image(blob=file, format="webp") as img:
                    with img.convert("png") as img2:
                        pic = img2.make_blob(format="png")
                # pic = await png_to_jpg(file)
        async with event.react("📤"):
            if is_animated:
                await event.reply_gif(gif)
            else:
                await event.reply_photo(pic)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def undelete(event, args, client):
    """
    Resend recently deleted messages in this group. Group only.
    Arguments:
        @mention(s): only fetch deleted messages from these users; default anyone
        -a: number of deleted messages to fetch (per user), default 1
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
                    await event.reply("-a: Sometimes i wonder…, reseting value…")
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


async def upscale_image(event: Event, args: str, client):
    """
    Upscale a replied image (or image document) and send it back
    as a raw png and as a jpeg.
    Requests are queued; react with ❌ to the command to cancel
    a queued request (requester, Owner, Sudo or Admin).
    Arguments: None
    """
    status_msg = None
    turn_id = f"{event.chat.id}:{event.id}"
    user = event.from_user.id
    cancel_handler_key = None
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")

    async def _cancel(e: Event, __, client):
        if not e.reaction:
            return
        if turn_id != f"{e.chat.id}:{e.reaction.key.ID}":
            return
        if e.reaction.text != "❌":
            return
        canceller = e.from_user.id
        if not (user == canceller or user_is_privileged(canceller)):
            group_info = await client.get_group_info(e.chat.jid)
            if not user_is_admin(canceller, group_info.Participants):
                return
        if turn().current == turn_id:
            return
        turn().remove(turn_id)
        await event.react("✖️")
        if status_msg:
            await status_msg.edit("*Cancelled*")

    try:
        if not event.reply_to_message:
            return await event.reply(
                "*Command can only be used when replying to an image.*"
            )
        if not conf.MODAL_UPSCALE_API and bot.disable_cic:
            return await event.reply("*CPU heavy commands are currently disabled.*")
        replied = event.reply_to_message
        if replied.document:
            if not replied.document.mimetype.startswith("image"):
                return await event.reply("*Replied document is not an image.*")
        elif not replied.image:
            return await event.reply(
                "*Command can only be used when replying to an image.*"
            )
        if replied.media.fileLength > 17939583:
            return await sticker_reply(event, args, client, True)
        turn().add(turn_id)
        status_msg = await event.reply("*…*")
        if replied.caption and replied.caption.startswith("Upscaled image:"):
            return await event.reply(
                "What?, initial upscale not good enough for you? 😒"
            )
        file = await replied.download()

        if waiting_for_turn():
            await event.react("⏰")
            await status_msg.edit(
                "*Waiting till previous upscaling process gets completed.*"
            )
            cancel_handler_key = bot.add_handler(_cancel)
            if not await wait_for_turn(turn_id):
                return
            await event.react("")
        # async with heavy_proc_lock:
        # Lock works now but eh i like the current implementation better
        await status_msg.edit("*Upscaling please wait…*")

        async def modal_upscale(img: bytes) -> bytes:
            return (await upscale_batch([img], 1800))[0]

        async def local_upscale(img: bytes) -> bytes:
            device = torch.device(
                "cuda" if torch.cuda.is_available() and not conf.NO_GPU else "cpu"
            )
            model = RealESRGAN(device, scale=4)
            model.load_weights("weights/RealESRGAN_x4.pth", download=True)
            image = Image.open(io.BytesIO(img)).convert("RGB")
            sr_image = await sync_to_async(model.predict, image)
            output = io.BytesIO()
            sr_image.save(output, format="png")
            output.name = "upscaled_image.png"
            return output.getvalue()

        if conf.MODAL_UPSCALE_API:
            try:
                raw = await modal_upscale(file)
            except Exception as e:  # noqa: BLE001
                log(Exception)
                if bot.disable_cic:
                    await event.react("❌")
                    await status_msg.edit(f"*Error:*\n{e}")
                    status_msg = None
                    return
                raw = await local_upscale(file)
        else:
            raw = await local_upscale(file)
        sz = len(raw)
        if sz > 2 << 30:
            msg = await event.reply("Can not send raw; file too large")
        elif sz > 100000000:
            msg = await event.reply_document(raw, "upscaled.png", "Upscaled image: Raw")
        else:
            msg = await event.reply_photo(raw, "Upscaled image: Raw")
        raw = await upscaled_png_to_jpg(raw)
        await msg.reply_photo(raw, "Upscaled image: Jpeg")
    except Exception as e:
        await logger(Exception)
        await event.react("❌")
        if status_msg:
            await status_msg.edit(f"*Error:*\n{e}")
        status_msg = None
    finally:
        if cancel_handler_key:
            bot.unregister(cancel_handler_key)
        if turn(turn_id):
            turn().advance()
            if status_msg:
                await status_msg.delete()


def move_oversized_in_place(original_list, max_mb=100):
    MAX_SIZE_BYTES = max_mb * 1024 * 1024
    overflow_list = []

    # keeps track of items that stay
    keep_index = 0

    for item in original_list:
        if len(item) > MAX_SIZE_BYTES:
            overflow_list.append(item)
        else:
            original_list[keep_index] = item
            keep_index += 1

    del original_list[keep_index:]
    return overflow_list


async def upscale_album(event: Event, args: str, client):
    """
    Upscale the images in a replied album via Modal and send them back
    as raw png and jpeg albums.
    Only available when the Modal upscale API is configured.
    Arguments: None
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not conf.MODAL_UPSCALE_API:
            return await event.reply("*Modal api not configured*")
        replied = event.reply_to_message
        if not replied:
            return await event.reply("Kindly reply to an album of images to upscale.")
        if replied.short_name != "album":
            return await event.reply("Message is not an album.")
        async with event.react("🗂️"):
            messages = await get_messages_by_album_id(event.chat.id, replied.id)
        if not messages:
            return await event.reply("*Replied album media(s) could not be retrieved.*")
        first = messages[0]
        if (
            first.image
            and first.caption
            and first.caption.startswith("Upscaled image:")
        ):
            return await event.reply(
                "What?, initial upscale not good enough for you? 😒"
            )
        medias = [m for m in messages if m.image and m.image.fileLength < 17939583]
        if not medias:
            return await event.reply("*Replied album had no upscale-able images.*")
        funcs = [media.download() for media in medias]
        async with event.react("📥"):
            files = await asyncio.gather(*funcs)
        upscaled: [bytes] = []
        async with event.react("👩🏻‍🏭"):
            for i in range(0, len(files), 2):
                pair = files[i : i + 2]
                try:
                    raws = await upscale_batch(pair, 1800)
                except Exception:
                    await logger()
                    continue
                upscaled.extend(raws)
            if not upscaled:
                return await event.reply("Upscaling failed")
            jpegs = [await upscaled_png_to_jpg(raw) for raw in upscaled]
            large_images = move_oversized_in_place(upscaled)
        async with event.react("📤"):
            u = await event.reply_album(upscaled, "Upscaled images: Raw")
            for f in large_images:
                if len(f) > 2 << 30:
                    await event.reply("Can not send raw; file too large")
                    continue
                await u.reply_document(f, "upscaled.png", "Upscaled image: Raw")
            await u.reply_album(jpegs, "Upscaled images: Jpeg")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def pick_random(event: Event, args: str, client):
    """
    Pick random item(s) from a list in the replied message.
    Arguments:
        -a: number of items to pick, default 1
        -m: header for the result; plain text without -m also works
        -s: item separator, default is a new line
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        replied = event.reply_to_message
        if not (replied and (replied.text or replied.caption)):
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
        text = replied.text or replied.caption
        items = text.split(arg.s or "\n")
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
    List the notes saved in this chat.
    Arguments:
        me / my notes: list only your notes
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
            msg_ += f"\n{i}. *{title}*{
                f' added by *{user_name}*' if event.chat.is_group and not filter_ else ''}"
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


async def save_notes(event: Event, args: str | None, client, silent=False):
    """
    Save a replied text/media message as a note in this chat.
    Retrieve with: get <note_name> or #note_name
    Arguments:
        note_name: name to save the note as (required)
        -c: remove the media caption
    Only the note's creator or an Owner can overwrite it.
    In groups, "rules" and "welcome" can only be set by admins.
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
        if not (replied := event.reply_to_message):
            return await event.reply("Can only save replied text or media.")
        if replied.is_actual_media and replied.media.viewOnce:
            return await event.reply("Saving view once is blocked.")
        if args.casefold() in ("all", "notes", "my notes", "me"):
            return await event.reply(f"Given note_name *{args}* is blocked.")
        if not bot.notes_dict.get(chat):
            bot.notes_dict[chat] = {}
        if event.chat.is_group and args.casefold() in ("rules", "welcome"):
            group_info = await bot.client.get_group_info(event.chat.jid)
            admin_user = user_is_admin(user, group_info.Participants)
            if not admin_user:
                return await event.reply(
                    f"Note with name '{args}' can only be set by an admin."
                )
            args = args.casefold()
        if (notes := bot.notes_dict[chat]).get(args):
            if (
                not user_is_owner(user)
                and user != notes[args]["user"]
                and args not in ("rules", "welcome")
            ):
                return await event.reply(
                    f"Note with name '{args}' already exists and can't be overwritten; Most likely because *you* did not add it."
                )
        if not (replied.text or replied.image or replied.media):
            return await event.reply("Can only save replied text or media.")
        status_msg = await event.reply("…") if not silent else None
        # note gen:
        note_type = str
        if replied.text:
            note = replied.text
        elif replied.image:
            if replied.image.fileLength < 5000000:
                note = await replied.download()
                note = [note, (replied.image.caption if not arg.c else "")]
                note_type = bytes
            else:
                note = replied.image
                note_type = Message
        elif replied.media:
            note = replied.media
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
        if silent:
            return True
        await status_msg.edit(f"_Saved replied message to notes with name:_ *{args}*")
    except DownloadError:
        await status_msg.edit("*Download Failed!*\nPlease ask that it be resent.")
        await status_msg.react("ℹ️")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def get_notes(event, args, client):
    """
    Get a saved note, or list the notes in this chat.
    Arguments:
        note_name: get that note (also works as #note_name)
        none / all / notes: list all notes
        me: list only your notes
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not args or (args and args.casefold() in ("all", "me", "notes", "my notes")):
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
            # newlines = "\n\n"
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
    Delete a saved note in this chat.
    Arguments:
        note_name: note to delete (your own, or any if Owner/Admin)
        all: delete all notes in this chat (Owner/Admin in groups)
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
                return await event.reply("*Permission denied.*")
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
    Get notes with #: #note_name gets a note, #notes lists all notes,
    #my notes lists your notes.
    AUTO FUNCTION
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
        if notes.get(event.text[1:]):
            return await get_notes(event, event.text[1:], None)
        await event.react("❓")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def tag_all_admins(event, args, client):
    """
    Tag group admins when a message contains @admin(s) or @mod(s).
    Plural form tags all admins; singular tags only the first.
    AUTO FUNCTION
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
            mentions_are_lids=event.lid_address,
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def tag_all_sudoers(event, args, client):
    """
    Tag bot sudoers when a group message contains @sudoer(s).
    Plural form tags all sudoers; singular tags only the first.
    AUTO FUNCTION
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
            mentions_are_lids=True,
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def tag_all_owners(event, args, client):
    """
    Tag bot owners when a group message contains @owner(s).
    Plural form tags all owners; singular tags only the first.
    AUTO FUNCTION
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
            mentions_are_lids=True,
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def tag_everyone(event: Event, args, client):
    """
    Tag everyone in a group when an Owner/Sudo/Admin sends @all or @everyone.
    WhatsApp's own @all tags get a reaction, or are deleted from
    non-admins if auto_del_all_tags is on and the bot is admin.
    AUTO FUNCTION
    """
    try:
        if not (text := (event.text or event.caption)):
            return
        if not event.chat.is_group:
            return
        if not (find_role_mentions(text, ["all", "everyone"])):
            return
        user = event.from_user.id
        group_info = await client.get_group_info(event.chat.jid)
        privileged = user_is_privileged(user) or user_is_admin(
            user, group_info.Participants
        )
        if event.media and event.media.contextInfo.nonJIDMentions:
            if (
                bot.group_dict.get(event.chat.id, {}).get("auto_del_all_tags")
                and not privileged
                and user_is_admin(bot.client.me.JID.User, group_info.Participants)
            ):
                await event.delete()
                raise StopHandlers("event was deleted due to an all tag")
            return await event.react("👀")
        if not privileged:
            return
        tags = tag_users(group_info.Participants)
        await clean_reply(
            event,
            event.reply_to_message,
            "reply",
            "_*Tagged everyone!*_",
            ghost_mentions=tags,
            mentions_are_lids=event.lid_address,
        )
    except StopHandlers:
        raise
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def pin_message(event, args, client):
    """
    [Owner | Sudo | Admin] Pin a replied message. Group only.
    Arguments:
        seconds: pin duration [Optional], default 7 days
    """
    if not event.chat.is_group:
        return await event.react("🚫")
    try:
        no = "https://media1.tenor.com/m/DUHB3rClTaUAAAAd/no-pernalonga.gif"
        user = event.from_user.id
        group_info = await client.get_group_info(event.chat.jid)
        if not user_is_privileged(user):
            if not user_is_admin(user, group_info.Participants):
                return await event.reply_sticker(
                    no,
                    name="Not allowed.",
                    packname="N.",
                )
        if not (replied := event.reply_to_message):
            return await event.reply("Please reply to a message to pin.")
        if not (args and args.isdigit()):
            await replied.pin()
        else:
            await replied.pin(int(args))
        await replied.react("📌")
        await event.react("✔️")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def unpin_message(event, args, client):
    "[Owner | Sudo | Admin] Unpin a replied message. Group only."
    if not event.chat.is_group:
        return await event.react("🚫")
    try:
        no = "https://media1.tenor.com/m/DUHB3rClTaUAAAAd/no-pernalonga.gif"
        user = event.from_user.id
        group_info = await client.get_group_info(event.chat.jid)
        if not user_is_privileged(user):
            if not user_is_admin(user, group_info.Participants):
                return await event.reply_sticker(
                    no,
                    name="Not allowed.",
                    packname="N.",
                )
        if not (replied := event.reply_to_message):
            return await event.reply("Please reply to a message to unpin.")

        await replied.unpin()
        await replied.react("")
        await event.react("✔️")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def purge_messages(event, args, client):
    """
    [Owner | Admin] Delete a range of messages. Group only; bot must be admin.
    Usage (always as a reply):
        --start: mark the replied message as the start point, then reply
                 to the end message with purge (session expires in 5 mins)
        --all: delete everything from the replied message up to this one
    """
    if not event.chat.is_group:
        return await event.react("🚫")
    try:
        no = "https://media1.tenor.com/m/DUHB3rClTaUAAAAd/no-pernalonga.gif"
        user = event.from_user.id
        group_info = await client.get_group_info(event.chat.jid)
        if not user_is_owner(user):
            if not user_is_admin(user, group_info.Participants):
                return await event.reply_sticker(
                    no,
                    name="Not allowed.",
                    packname="N.",
                )
        if not user_is_admin(bot.client.me.JID.User, group_info.Participants):
            return await event.reply("I need to be an admin to purge messages.")

        if not (replied := event.reply_to_message):
            return await event.reply(
                "Please reply to a message to mark a start point for purging."
            )
        arg, args = get_args(
            ["--start", "store_true"],
            ["--all", "store_true"],
            to_parse=args or "",
            get_unknown=True,
        )
        chat_id = event.chat.id
        msg_id = event.reply_to_message.id if event.reply_to_message else event.id

        if arg.start:
            purge_sessions[(chat_id, user)] = {"start_id": msg_id, "time": time.time()}
            return await event.reply(
                f"Purge session started from message ID: `{msg_id}`.\n"
                f"Reply to the ending message with `{conf.CMD_PREFIX}purge` to start purge.\n"
                "Session expires in 300 seconds."
            )
        if arg.all:
            messages = await get_messages_between(chat_id, msg_id, event.id)
            if not messages:
                return await event.reply("No messages found to purge.")
        else:
            session = purge_sessions.get((chat_id, user))
            if not session:
                return await event.reply(
                    f"No starting point for purge supplied.\nFor help send {conf.CMD_PREFIX}purge -h"
                )
            if time.time() - session["time"] > 300:
                del purge_sessions[(chat_id, user)]
                return await event.reply(
                    f"Purge session timed out. Start a new one with `{conf.CMD_PREFIX}purge --start`."
                )
            end_msg_id = event.reply_to_message.id
            start_id = session["start_id"]
            del purge_sessions[(chat_id, user)]
            messages = await get_messages_between(chat_id, start_id, end_msg_id)
            if not messages:
                return await event.reply("No messages found to purge.")
        await event.react("🚮")
        for msg in messages:
            await msg.delete()
        await event.react("")
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
        user = event.user.id
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
        msg_rank["server"] = 0 if event.lid_address else 1
        msg_rank["total"] = msg_rank.setdefault("total", 0) + value
        bot.msg_leaderboard_counter += 1
    except Exception:
        await logger(Exception)


async def msg_ranking(event, args, client):
    """
    Get this group's message leaderboard. Group only.
    Arguments:
        -f / --full: show the full ranking
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
        return await event.reply(msg)
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
        sorted(
            ((k, v) for k, v in msg_rank_dict.items() if isinstance(v, int)),
            key=lambda item: item[1],
            reverse=True,
        )
    )

    for user in list(sorted_ms_rank_dict.keys()):
        if user in ("total", "server", "period"):
            continue
        value = sorted_ms_rank_dict[user]
        user_info = await get_user_info(user, server)
        msg += f"{i}. {(user_info.PushName or '👤 Unknown') if not tag else ('@' +
                                                                            user)} · {human_format_num(value)}\n"
        medals = get_medals(chat_id, user)
        msg += f"    └{medals}\n" if medals else ""
        i += 1
        if i > 10 and not full:
            break
    if not msg:
        return
    act_mem = len(msg_rank_dict.keys()) - 2
    total_msg = msg_rank_dict.get("total")
    return f"📈 *MESSAGE LEADERBOARD*\n{msg}\n👥 *Participants:* {
        human_format_num(act_mem)}\n✉️ *Total messages:* {
        human_format_num(total_msg)}"


def get_medals(chat_id, user):
    group = bot.group_dict.setdefault(chat_id, {})
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
            if handled_self_leave(gc_msg):
                await save2db2(bot.group_dict, "groups")
                return
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


async def handle_self_join(message):
    # log(e=message)
    # if message.Type != "linked_group_join":
    #     return
    log(e=f"Reason: {message.Reason or 'None'}")
    log(e=f"Name: {message.GroupInfo.GroupName.Name}")
    gc_jid = message.GroupInfo.JID
    bot.group_dict.get(gc_jid.User, {}).update({"left": False})
    await save2db2(bot.group_dict, "groups")
    log(e=f"Joined group with JID: {gc_jid}")


def handled_self_leave(gc_event):
    user = gc_event.Leave[0].User
    server = gc_event.Leave[0].Server
    if server == "lid":
        if bot.client.me.LID.User != user:
            return
    else:
        if bot.client.me.JID.User != user:
            return
    bot.group_dict.get(gc_event.JID.User, {}).update({"left": True})
    if gc_event.Sender.User != user:
        info = "Banned from group"
    else:
        info = "Left group"
    log(e=f"{info} with JID: {gc_event.JID}")
    bot.temp2 = gc_event
    return True


async def goodbye_msg(gc_event):
    msg1 = "_It was nice knowing you, {}!_"
    msg2 = "*Another one bites the dust...!*\n@{} _banned_ @{}."
    user = gc_event.Leave[0].User
    server = gc_event.Leave[0].Server
    user_info = await get_user_info(user)
    if (doer := gc_event.Sender.User) != user:
        msg = msg2.format(doer, user)
    else:
        msg = msg1.format(user_info.PushName or "@" + user)
    await bot.client.send_message(
        gc_event.JID,
        msg,
        mentions_are_lids=(server == "lid"),
    )


async def welcome_msg(gc_event):
    group_info = await bot.client.get_group_info(gc_event.JID)
    txt, any_ = s_welcome_msg(gc_event, group_info)
    if not (txt or any_):
        txt = "*Hi there* {0}, Welcome to *{1}*!\nRemember to be respectful and follow the rules."
        txt += "\n\n*Joined through:* {2}"
    chat_name = group_info.GroupName.Name
    r = None
    if (gc := bot.group_dict.get(gc_event.JID.User, {})) and (r := gc.get("rules")):
        user_jid = bot.client.me.JID
    for jid in gc_event.Join:
        user_name = f"@{jid.User}"
        if not any_:
            msg = await bot.client.send_message(
                gc_event.JID,
                txt.format(user_name, chat_name, gc_event.JoinReason),
                mentions_are_lids=(jid.Server == "lid"),
            )
        elif not isinstance(any_, bytes):
            if hasattr(any_, "caption"):
                any_.caption = any_.caption.format(
                    user_name, chat_name, gc_event.JoinReason
                )
            any_.contextInfo.mentionedJID.append(Jid2String(jid))
            field_name = (
                any_.__class__.__name__[0].lower() + any_.__class__.__name__[1:]
            )
            message = Message(**{field_name: any_})
            msg = await bot.client.send_message(
                gc_event.JID,
                message,
                mentions_are_lids=(jid.Server == "lid"),
            )
        else:
            msg = await bot.client.send_image(
                gc_event.JID,
                any_,
                txt.format(user_name, chat_name, gc_event.JoinReason),
                mentions_are_lids=(jid.Server == "lid"),
            )
        if r:
            evt = construct_msg_and_evt(
                gc_event.JID.User,
                user_jid.User,
                msg.ID,
                None,
                "g.us",
                user_jid.Server,
                msg.Message,
            )
            evt.lid_address = gc.get("lid_address", False)
            await s_rules(evt, False)


def s_welcome_msg(gc_event, group_info):
    chat = gc_event.JID.User
    gc = bot.group_dict.get(chat, {})
    if not (msg := gc.get("welcome_msg")) or not isinstance(msg, str):
        return "", None
    try:
        if msg not in ("notes", "topic"):
            return msg, None
        elif msg == "topic":
            topic = group_info.GroupTopic.Topic
            return topic, None
        notes = bot.notes_dict[chat]
        if not (u_note := notes.get("welcome")):
            return "", None
        user, note, note_type = (
            u_note.get("user"),
            u_note.get("note"),
            u_note.get("note_type"),
        )
        if note_type == str:
            return note, None
        elif note_type == bytes:
            return note[1], note[0]
        elif note_type == Message:
            note = copy.deepcopy(note)
            # if hasattr(note, "viewOnce"):
            # note.viewOnce = False
            return "", note
    except Exception:
        log(Exception)
        return "", None


async def save_filter(event: Event, args: str, client):
    """
    [Owner | Sudo | Admin] Save a replied text/media message as a filter. Group only.
    The bot replies with it whenever a message contains filter_name.
    Arguments:
        filter_name: text to match (min 3 characters unless -a or -m)
        -a: match if all words of filter_name appear anywhere, in any order
        -m: match filter_name only as whole word(s)
        -c: remove the media caption
    Only the filter's creator or an Owner can overwrite it.
    """
    chat = event.chat.id
    user = event.from_user.id
    if not event.chat.is_group:
        return
    if not user_is_privileged(user):
        group_info = await bot.client.get_group_info(event.chat.jid)
        if not user_is_admin(user, group_info.Participants):
            return
    if not user_is_allowed(user):
        return await event.react("⛔")
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
        replied = event.reply_to_message
        if not (
            replied.text or replied.media or replied.sticker or replied.stickerPack
        ):
            return await event.reply(
                "Can only save replied text or media as filter reply."
            )
        if args.casefold() in ("all", "notes", "my notes", "me") or (
            len(args) < 3 and not (arg.a or arg.m)
        ):
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
        if replied.text:
            new_filter = replied.text
        elif replied.image:
            if replied.image.fileLength < 5000000:
                new_filter = await replied.download()
                new_filter = [
                    new_filter,
                    (replied.image.caption if not arg.c else ""),
                ]
                filter_type = bytes
            else:
                new_filter = replied.image
                filter_type = Message
        elif new_filter := replied.stickerPack:
            filter_type = Message
            if not new_filter.publisher:
                new_filter.publisher = bot.client.me.PushName
        elif new_filter := replied.media:
            filter_type = Message
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
    List the filters saved in this group. Group only.
    Arguments:
        me / my filters: list only your filters
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
    Delete a saved filter in this group. Group only.
    Arguments:
        filter_name: filter to delete (your own, or any if Owner/Admin)
        all: (Owner | Admin) delete all filters in this group
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
                return await event.reply("*Permission denied.*")
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
    Reply with saved filters that match a group message (max 2 per message).
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


async def to_media(event: Event, _, client):
    """
    If an image/video/gif document's caption contains (asm),
    resend it as media with (asm) removed from the caption.
    AUTO FUNCTION
    """
    user = event.from_user.id
    try:
        if not event.document:
            return
        mimetype: str = event.document.mimetype
        if not mimetype.startswith(("image", "video")):
            return
        if not ((caption := event.caption) and "(asm)" in caption.casefold()):
            return
        if not user_is_privileged(user):
            if not chat_is_allowed(event):
                return
            if not user_is_allowed(user):
                return await event.react("⛔")
        caption = re.sub(r"\(asm\)", "", caption, count=1, flags=re.IGNORECASE).strip()
        is_gif = mimetype == "image/gif"
        target = event.reply_to_message or event
        async with event.react("📥"):
            file = await event.download()
        if mimetype.startswith("image"):
            if not is_gif:
                file = await image_to_png(file)
        else:
            is_avc = False
            async with AFFmpeg(file) as ffmpeg:
                streams = (await ffmpeg.extract_info()).streams
                try:
                    is_avc = any(s.is_avc for s in streams)
                except Exception:
                    pass
                if not is_avc:
                    async with event.react("🧑‍🏭"):
                        file = await ffmpeg.to_mp4_reencode()

        async with event.react("📤"):
            if is_gif:
                await target.reply_gif(file, caption)
            elif mimetype.startswith("video"):
                await target.reply_video(file, caption)
            else:
                await target.reply_photo(file, caption)
    except Exception:
        await logger(Exception)


async def repeat(event: Event, args: str, client):
    """
    Repeat a replied message. Group only.
    Arguments:
        -nq: don't quote
        -x: repeat a number of times, max 5 (Owner/Sudo/Admin only)
        -uv: remove view once
        -vo: force view once
        -cc: clear caption
        -C: custom caption
        -f: mark as forwarded
        -ff: mark as forwarded many times
        -rf: remove forwarded mark
        -asm: resend an image/video/gif document as media
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
        if not (replied := event.reply_to_message):
            return await event.reply("*Kindly reply to a message.*")
        args = args or ""
        arg, args = get_args(
            ["-nq", "store_false"],
            ["-uv", "store_true"],
            ["-vo", "store_true"],
            ["-cc", "store_true"],
            ["-f", "store_true"],
            ["-ff", "store_true"],
            ["-rf", "store_true"],
            ["-asm", "store_true"],
            "-x",
            "-C",
            to_parse=args,
            get_unknown=True,
        )
        if arg.asm:
            if not replied.document:
                return await event.reply("Kindly reply to a document.")
            mimetype: str = replied.document.mimetype
            if not mimetype.startswith(("image", "video")):
                return await event.reply("Not an image or video")
            async with event.react("📥"):
                file = await replied.download()
            async with event.react("📤"):
                if mimetype == "image/gif":
                    await event.reply_gif(file, replied.caption, quote=arg.nq)
                elif mimetype.startswith("video"):
                    await event.reply_video(file, replied.caption, arg.nq)
                else:
                    await event.reply_photo(file, replied.caption, arg.nq)
            return
        if arg.uv or arg.vo:
            if replied.is_actual_media:
                replied.media.viewOnce = True if arg.vo else False
        if arg.cc or arg.C:
            if replied.is_actual_media:
                replied.media.caption = arg.C or ""
        if arg.f or arg.ff or arg.rf:
            if hasattr(replied.media, "contextInfo"):
                score = 0
                if arg.f:
                    score = 1
                elif arg.ff:
                    score = random.randint(127, 999)
                replied.media.contextInfo.forwardingScore = score
                replied.media.contextInfo.isForwarded = (arg.f or arg.ff) and not arg.rf
        if arg.x and not arg.x.isdigit():
            arg.x = ""
        if arg.x and not user_is_privileged(user):
            group_info = await bot.client.get_group_info(event.chat.jid)
            if not user_is_admin(user, group_info.Participants):
                arg.x = ""
        no = int(arg.x) if arg.x and not arg.x == "0" else 1
        no = min(no, 5)
        for _ in range(no):
            await event.reply(message=(replied.text or replied.media), quote=arg.nq)
            arg.nq = False
            await asyncio.sleep(1)
    except Exception:
        await logger(Exception)


async def tikmate(event: Event, args: str, client):
    """
    Download TikTok videos/images via Tikmate.
    Usage:
        Pass TikTok link(s) as argument, or reply to a message containing them.
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        base_dir = f"media_dl/{event.chat.id}:{event.id}"
        rargs = ""
        if replied := event.reply_to_message:
            rargs = replied.text or replied.caption
        if not (txt := (rargs or args)):
            return await event.reply("kindly supply a url")
        extractor = URLExtract()
        urls = extractor.find_urls(txt)
        if not urls:
            return await event.reply("*No link found in your message*")
        urls = list(dict.fromkeys(urls))
        for url in urls:
            if "www.tiktok.com/tiktoklite" in url:
                continue
            async with event.react("📥"):
                items = await TikmateAsync().download_tikmate(
                    url,
                    base_dir,
                )
            if not items:
                await event.reply(f"Tikmate returned no media for:\n{url}")
                continue
            caption = items[0].caption
            caption = f"*{caption}*" if caption else caption
            groups = defaultdict(list)
            for item in items:
                groups[item.media_type].append(item.local_path)
            async with event.react("📤"):
                for media_type, paths in groups.items():
                    if media_type == "image":
                        for i, file in enumerate(paths):
                            jpg = await png_to_jpg(file)
                            paths[i] = jpg
                    if len(paths) > 1:
                        await event.reply_album(paths, caption)
                    else:
                        if media_type == "video":
                            await event.reply_video(paths[0], caption)
                        else:
                            await event.reply_photo(paths[0], caption)
    except Exception:
        await logger(Exception)
        await event.react("✖️")
    finally:
        s_remove(base_dir, folders=True)
        raise StopHandlers


async def set_rules(event, args, client):
    """
    [Admins Only] Set the group rules. Group only.
    Usage:
        Reply to a text or media message to use as the rules.
        Media rules are saved as the "rules" note.
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
        group_info = await bot.client.get_group_info(event.chat.jid)
        admin_user = user_is_admin(user, group_info.Participants)
        if not admin_user:
            return await event.reply("*Command can only be used by an admin.*")
        if not (replied := event.reply_to_message):
            return await event.reply("*Kindly reply to a message.*")
        gc = bot.group_dict.setdefault(event.chat.id, {})
        if replied.is_actual_media or replied.sticker:
            status = await save_notes(event, "rules", client, True)
            if status:
                gc["rules"] = "notes"
                gc["lid_address"] = event.lid_address
                await save2db2(bot.group_dict, "groups")
                return await event.react("✅")
        elif text := replied.text:
            gc["rules"] = text
            gc["lid_address"] = event.lid_address
            await save2db2(bot.group_dict, "groups")
            return await event.react("✅")
        else:
            return await event.react("✖️")

    except Exception:
        await logger(Exception)


async def delete_rules(event, args, client):
    """
    [Admins Only] Delete the group rules. Group only.
    Note: Does not delete the "rules" note if one was set!
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
        group_info = await bot.client.get_group_info(event.chat.jid)
        admin_user = user_is_admin(user, group_info.Participants)
        if not admin_user:
            return await event.reply("*Command can only be used by an admin.*")
        gc = bot.group_dict.get(event.chat.id, {})
        if not gc.get("rules"):
            return await event.reply("*No rules were set.*")
        else:
            gc["rules"] = None
            await save2db2(bot.group_dict, "groups")
            return await event.react("✅")
    except Exception:
        await logger(Exception)


async def set_welcome(event, args, client):
    """
    [Admins Only] Set the group welcome message. Group only.
    Usage:
        Reply to a text or media message to use as the welcome message.
        Media is saved as the "welcome" note.
        Extra Formatting:
          {0} tag user
          {1} group name
          {2} join reason
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
        group_info = await bot.client.get_group_info(event.chat.jid)
        admin_user = user_is_admin(user, group_info.Participants)
        if not admin_user:
            return await event.reply("*Command can only be used by an admin.*")
        if not (replied := event.reply_to_message):
            return await event.reply("*Kindly reply to a message.*")
        gc = bot.group_dict.setdefault(event.chat.id, {})
        if replied.is_actual_media or replied.sticker:
            status = await save_notes(event, "welcome", client, True)
            if status:
                gc["welcome_msg"] = "notes"
                gc["lid_address"] = event.lid_address
                await save2db2(bot.group_dict, "groups")
                return await event.react("✅")
        elif text := replied.text:
            gc["welcome_msg"] = text
            gc["lid_address"] = event.lid_address
            await save2db2(bot.group_dict, "groups")
            return await event.react("✅")

        return await event.react("✖️")

    except Exception:
        await logger(Exception)


async def unset_welcome(event, args, client):
    """
    [Admins Only] Unset the group welcome message. Group only.
    Note: Does not delete the "welcome" note if one was set!
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
        group_info = await bot.client.get_group_info(event.chat.jid)
        admin_user = user_is_admin(user, group_info.Participants)
        if not admin_user:
            return await event.reply("*Command can only be used by an admin.*")
        gc = bot.group_dict.get(event.chat.id, {})
        if not gc.get("welcome_msg"):
            return await event.reply("*No welcome message was set.*")
        else:
            gc["welcome_msg"] = None
            await save2db2(bot.group_dict, "groups")
            return await event.react("✅")
    except Exception:
        await logger(Exception)


async def get_rules(event, args, client):
    """
    Get this group's rules sent to you in PM. Group only.
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
        return await s_rules(event)
    except Exception:
        await logger(Exception)


async def s_rules(event, pm=True):
    chat = event.chat.id
    gc = bot.group_dict.get(event.chat.id, {})
    if not (rules := gc.get("rules")) or not isinstance(rules, str):
        if pm:
            return await clean_reply(
                event,
                event.reply_to_message,
                "reply",
                "*No Rules Set Yet!*",
                reply_privately=pm,
            )
        return
    try:
        if rules not in ("notes", "topic"):
            return await clean_reply(
                event, event.reply_to_message, "reply", rules, reply_privately=pm
            )
        elif rules == "topic":
            gc_info = await event.client.get_group_info(event.chat.jid)
            rules = gc_info.GroupTopic.Topic or "*No group Description.*"
            return await clean_reply(
                event, event.reply_to_message, "reply", rules, reply_privately=pm
            )
        notes = bot.notes_dict[chat]
        if not (u_note := notes.get("rules")):
            return
        user, note, note_type = (
            u_note.get("user"),
            u_note.get("note"),
            u_note.get("note_type"),
        )
        if note_type == str:
            return await clean_reply(
                event, event.reply_to_message, "reply", note, reply_privately=pm
            )
        elif note_type == bytes:
            return await clean_reply(
                event,
                event.reply_to_message,
                "reply_photo",
                note[0],
                note[1],
                reply_privately=pm,
            )
        elif note_type == Message:
            note = copy.deepcopy(note)
            newlines = "\n\n"
            if hasattr(note, "viewOnce"):
                note.viewOnce = False
            return await clean_reply(
                event,
                event.reply_to_message,
                "reply",
                message=note,
                reply_privately=pm,
            )
    except Exception:
        await logger(Exception)


async def save_reminder(event: Event, args: str, client):
    """
    Get reminded of the replied message (or this one) at a future time.
    Arguments:
        time: when to remind, e.g. "2hrs 30mins", "in 3 days",
              "next friday at noon"
    """
    user = event.from_user.id
    if not (user_is_privileged(user)):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        parsed_time = parse_reminder_time_hybrid(args)
        if parsed_time is None:
            return await event.reply("Invalid time.")
        _id = str(uuid.uuid4())
        chat = Jid2String(event.chat.jid)
        store = {
            "id": _id,
            "message": (event.reply_to_message or event).message,
            "user": user,
            "time": parsed_time,
            "lid_address": event.lid_address,
        }
        bot.remind_dict.setdefault(chat, {}).setdefault(user, {})[_id] = store
        await save2db2(bot.remind_dict, "reminders")
        await schedule_reminder_async(_id, store, chat, user)
        await event.reply(
            "Reminder set for " + get_date_from_isostr(parsed_time) + f"\n*ID:* _{_id}_"
        )
    except Exception:
        await logger(Exception)


async def list_reminders(event, args, client):
    """
    List your reminders in this chat, with their IDs.
    """
    user = event.from_user.id
    if not (user_is_privileged(user)):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:

        chat = Jid2String(event.chat.jid)
        if not (gcr := bot.remind_dict.get(chat)):
            return await event.reply("No reminders found here.")
        if not (gcru := gcr.get(user)):
            return await event.reply("No reminders found for user.")

        msg = ""
        for _id, store in gcru.items():
            msg += f"\n- *{_id}*  🔔 @{get_date_from_isostr(store['time'])}"
        if msg == "":
            return await event.reply("No reminders found for user.")
        await event.reply(f"*Reminders:*{msg}")
    except Exception:
        await logger(Exception)


async def delete_reminders(event, args, client):
    """
    Delete your reminders in this chat.
    Get IDs with: all_reminders
    Arguments:
        id: ID of the reminder to delete
        all: delete all your reminders in this chat
    """
    user = event.from_user.id
    if not (user_is_privileged(user)):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        chat = Jid2String(event.chat.jid)
        if not (gcr := bot.remind_dict.get(chat)):
            return await event.reply("No reminders found here.")
        if not (gcru := gcr.get(user)):
            return await event.reply("No reminders found for user.")
        if args == "all":
            for _id in gcru:
                cancel_reminder(_id)
            gcr[user] = {}
            await save2db2(bot.remind_dict, "reminders")
            return await event.reply("All reminders have been deleted.")
        if not gcru.get(args):
            return await event.reply("Reminder with given ID not found.")
        gcru.pop(args)
        cancel_reminder(args)
        await save2db2(bot.remind_dict, "reminders")
        await event.reply(f"Deleted reminder with ID: {args}")
    except Exception:
        await logger(Exception)


async def auto_del_msg(event: Event, _, __):
    user = event.from_user.id
    if user_is_privileged(user):
        return
    chat_id = event.chat.id
    group_info: dict = bot.group_dict.setdefault(chat_id, {})
    muted: set = group_info.setdefault("muted", set())
    if user in muted:
        try:
            await event.delete()
            raise StopAutoHandlers("user is muted")
        except StopAutoHandlers:
            raise
        except Exception:
            pass


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
        poll_msg_, msg_ = await create_sudo_button(
            title, button_dict, event.chat.jid, user
        )
        msg_id = msg_.ID
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
bot.add_handler(to_media)
bot.add_handler(get_notes2)
bot.add_handler(tag_everyone)
bot.add_handler(detect_filters)
bot.add_handler(tag_all_admins)
bot.add_handler(tag_all_owners)
bot.add_handler(tag_all_sudoers)
bot.add_handler(rec_msg_ranking)

bot.add_handler(to_doc, "doc")
bot.add_handler(getfps, "fps")
bot.add_handler(to_mp3, "mp3")
bot.add_handler(tools, "tools")
bot.add_handler(get_notes, "get")
bot.add_handler(repeat, "repeat")
bot.add_handler(undelete, "undel")
bot.add_handler(get_rules, "rules")
bot.add_handler(pin_message, "pin")
bot.add_handler(tikmate, "tikmate")
bot.add_handler(compress, "compress")
bot.add_handler(kang_sticker, "kang")
bot.add_handler(pick_random, "random")
bot.add_handler(set_rules, "setrules")
bot.add_handler(getminfo, "mediainfo")
bot.add_handler(unpin_message, "unpin")
bot.add_handler(purge_messages, "purge")
bot.add_handler(delete_rules, "delrules")
bot.add_handler(list_filters, "filters")
bot.add_handler(sanitize_url, "sanitize")
bot.add_handler(screenshot, "screenshot")
bot.add_handler(upscale_image, "upscale")
bot.add_handler(msg_ranking, "msg_ranking")
bot.add_handler(stickerize_image, "sticker")
bot.add_handler(sticker_to_image, "stick2img")
bot.add_handler(upscale_album, "batch_upscale")
bot.add_handler(list_reminders, "all_reminders")
bot.add_handler(sanitize_video, "sanitize_video")


bot.add_handler(set_welcome, "setwelcome")
bot.add_handler(unset_welcome, "unsetwelcome")


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
bot.add_handler(
    delete_reminders,
    "del_reminder",
    require_args=True,
)
bot.add_handler(
    save_reminder,
    "remindme",
    require_args=True,
)

# sequential autos
bot.add_handler(auto_del_msg, SEQUENTIAL_AUTO)

# test
bot.add_handler(test_button, "button")
