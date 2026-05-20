import asyncio
import os

from clean_links.clean import clean_url
from urlextract import URLExtract

from bot.config import bot
from bot.pkgs.insta_dl import is_valid_instagram_url
from bot.pkgs.pinterest_dl import is_valid_pinterest_url
from bot.pkgs.tiktok_dl import is_valid_tiktok_url, resolve_short_url
from bot.utils.bot_utils import png_to_jpg, sync_to_async
from bot.utils.log_utils import group_logger, log, logger
from bot.utils.media_dl_utils import Listener as MediaListener
from bot.utils.media_dl_utils import MediaHelper as MediaDLHelper
from bot.utils.msg_utils import (
    chat_is_allowed,
    extract_bracketed_prefix,
    wrap_lines_with_asterisks,
)
from bot.utils.os_utils import dir_exists, file_exists, s_remove, size_of
from bot.utils.ytdl_utils import (
    DummyListener,
    YoutubeDLHelper,
    extract_info,
    get_video_name,
    is_supported,
    is_valid_trim_args,
)


async def folder_upload(folder, event, status_msg, audio, listener):
    if not dir_exists(folder):
        return

    for path, subdirs, files in os.walk(folder):
        subdirs.sort()
        if not files:
            if not os.listdir(path):
                continue
        if "yt-dlp-thumb" in path:
            continue
        i = len(files)
        t = 1
        for name in sorted(files):

            if listener.is_cancelled:
                await status_msg.edit("*Upload has been cancelled!*")
                return

            name_, ext_ = os.path.splitext(name)
            base_name = get_video_name(name_)
            file = os.path.join(path, name)
            await status_msg.edit(f"[{t}/{i}]\nUploading *{name}*…")

            if size_of(file) >= 100000000:
                await event.reply(f"*{name} too large to upload.*")
                await asyncio.sleep(3)
                continue

            if ext_ in ("png", "jpg", "jpeg") and name_.startswith(
                path.split("/", maxsplit=2)[-1]
            ):
                event = await event.reply_photo(file, f"*{name_}*")
            elif audio and file.endswith("mp3"):
                photo = await get_audio_thumbnail(file)
                reply = await event.reply_photo(photo, f"*{base_name}*")
                event = await reply.reply_audio(file)
            elif file.endswith("mp4"):
                event = await event.reply_video(file, f"*{base_name}*")
            await asyncio.sleep(3)
            t += 1


async def get_audio_thumbnail(file):
    for x in ["webp", "jpg", "png"]:
        image = file[:-3] + x
        if file_exists(image):
            break
    else:
        return None

    with open(image, "rb") as pfile:
        webp = pfile.read()
    return await png_to_jpg(webp)


async def youtube_reply(event, args, client):
    """
    Download and upload sent video from sent YouTube link
    """
    try:
        if not event.text:
            return
        if event.is_edit:
            return
        if "#no_ytdl" in event.text.casefold():
            return
        if event.chat.is_group and not chat_is_allowed(event):
            return
        if not bot.group_dict.get(event.chat.id, {}).get("ytdl"):
            return
        trimmed = will_trim = False
        extractor = URLExtract()
        text = args or event.text
        urls = extractor.find_urls(text)
        if not urls:
            return
        supported_links = []
        for url in urls:
            url = clean_url(url)
            extractors_checkers = [
                is_supported,
                is_valid_instagram_url,
                is_valid_pinterest_url,
                is_valid_tiktok_url,
            ]
            for check in extractors_checkers:
                if check(url):
                    supported_links.append(url)
                    break
        if not supported_links:
            return
        job = list(supported_links)
        t_args = extract_bracketed_prefix(text)
        while job:
            try:
                alt_listener = listener = MediaListener(job[0])
                tryAlt = False

                if is_valid_tiktok_url(listener.link):
                    tryAlt = listener.is_tiktok = True
                elif is_valid_instagram_url(listener.link):
                    tryAlt = listener.is_insta = True
                elif is_valid_pinterest_url(listener.link):
                    tryAlt = listener.is_pintrest = True
                if tryAlt:
                    if await media_reply(event, listener, t_args):
                        job.pop(0)
                        continue
                audio = False
                twi = False
                is_tiktok = False
                _format = "bv*[ext=mp4][vcodec~='h264|avc1'][filesize<100M][height<={0}]+ba[ext=m4a]/b[ext=mp4][vcodec~='h264|avc1'][filesize<100M][height<={0}] / bv*+ba/b"
                _alt_format = "bv*[ext=mp4][vcodec~='h264|avc1'][height<={0}]+ba/b[ext=mp4][vcodec~='h264|avc1'][height<={0}] / bv*+ba/b"
                listener = DummyListener(job[0])
                ytdl = YoutubeDLHelper(listener)
                if "music" in listener.link:
                    audio = True
                    _format = _alt_format = "ba/b-mp3{0}"
                    quality = "-"
                elif "shorts" in listener.link and "(720p)" in text:
                    quality = "1280"
                else:
                    for qua in ["1080", "480", "360", "270", "240", "144"]:
                        if f"({qua}p)" in text:
                            quality = qua
                            break
                    else:
                        quality = "720"
                if alt_listener.is_tiktok:
                    try:
                        url = await resolve_short_url(listener.link, ".cookies.txt")
                        if url:
                            listener.link = url
                    except Exception:
                        log(Exception)
                try:
                    result = await sync_to_async(extract_info, listener.link)
                except ValueError as w:
                    await group_logger(e=w, warning=True)
                    await asyncio.sleep(1)
                    job.pop(0)
                    continue
                if result.get("is_live") or result.get("live_status") == "live":
                    return await event.reply("*It's a Live video XD*")
                playlist = "entries" in result
                if not (trimmed or playlist) and t_args:
                    trimmed = True
                    if not is_valid_trim_args(t_args, total_dur=result.get("duration")):
                        (
                            await event.reply(f"{t_args} is not a valid trim argument!")
                            if "-" in t_args
                            else None
                        )
                        t_args = None
                if result.get("extractor").casefold() != "youtube":
                    _format = _alt_format
                elif result.get("extractor").casefold() == "twitter":
                    twi = True
                elif result.get("extractor").casefold() == "tiktok":
                    is_tiktok = True
                status_msg = await event.reply("*Downloading…*")
                await ytdl.add_download(
                    f"ytdl/{event.chat.id}:{event.id}",
                    _format.format(quality),
                    playlist,
                    status_msg,
                    trim_args=t_args,
                    twi=twi,
                    is_tiktok=is_tiktok,
                )
                if not ytdl.download_is_complete:
                    if listener.is_cancelled and listener.error:
                        await status_msg.edit(listener.error)
                    job.pop(0)
                    await ytdl.clean_up()
                    s_remove(ytdl.folder, folders=True)
                    continue
                await status_msg.edit("Download completed, Now uploading…")
                file = f"{ytdl.folder}/{ytdl.name}"
                if not playlist:
                    if not file_exists(file):
                        raise Exception(f"File: {file} not found!")
                    if size_of(file) > 100000000:
                        await status_msg.edit(
                            "*Upload failed, Video is too large!*\nTry with lower quality."
                        )
                        await ytdl.clean_up()
                        s_remove(ytdl.folder, folders=True)
                        job.pop(0)
                        continue
                    log(e=f"Uploading {file}…")
                    base_name = get_video_name(ytdl.base_name)
                    if not audio:
                        await event.reply_video(file, f"*{base_name}*")
                    else:
                        photo = await get_audio_thumbnail(file)
                        if photo:
                            reply = await event.reply_photo(photo, f"*{base_name}*")
                            await reply.reply_audio(file)
                        else:
                            await event.reply_audio(file)
                else:
                    await folder_upload(
                        ytdl.folder, event, status_msg, audio, ytdl._listener
                    )
                await ytdl.clean_up()
                s_remove(ytdl.folder, folders=True)
                await status_msg.delete() if not ytdl._listener.is_cancelled else None
                job.pop(0)
            except Exception:
                await logger(Exception)
                await ytdl.clean_up()
                job.pop(0)
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def media_reply(event, listener, t_args=None) -> bool:
    media_dl = MediaDLHelper(listener)
    status_msg = await event.reply("*Downloading…*")
    downloads = await media_dl.add_download(
        f"media_dl/{event.chat.id}:{event.id}",
        message=status_msg,
        trim_args=t_args,
    )
    if not (media_dl.download_is_complete or downloads):
        if listener.is_cancelled and listener.error:
            await status_msg.edit("*Download Failed;* Trying fallback...")
        await media_dl.clean_up()
        s_remove(media_dl.folder, folders=True)
        return listener.user_cancelled
    await status_msg.edit("Download completed, Now uploading…")
    for file in downloads:
        file_name = file.local_path
        if not file_exists(file_name):
            await logger(e=f"File: {file_name} not found!", error=True)
            continue
        if size_of(file_name) > 100000000:
            await event.reply(
                "*Upload failed, Video is too large!*\nTry with lower quality."
            )
            continue
        log(e=f"Uploading {file_name}…")

        if file.media_type == "video":
            await event.reply_video(file_name, wrap_lines_with_asterisks(file.caption))
        elif file.media_type == "image":
            await event.reply_photo(file_name, wrap_lines_with_asterisks(file.caption))
        elif file.media_type == "gif":
            await event.reply_gif(
                file_name, wrap_lines_with_asterisks(file.caption), as_gif=True
            )
        else:
            await logger(e=f"Unknown media type: {file.media_type}", error=True)
    await media_dl.clean_up()
    s_remove(media_dl.folder, folders=True)
    await status_msg.delete() if not media_dl._listener.is_cancelled else None
    return True
