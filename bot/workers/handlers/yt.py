import asyncio
import os

from clean_links.clean import clean_url
from urlextract import URLExtract

from bot.config import bot
from bot.pkgs.insta_dl import is_valid_instagram_url
from bot.utils.bot_utils import png_to_jpg, sync_to_async
from bot.utils.insta_dl_utils import InstagramHelper as InstagramDLHelper
from bot.utils.insta_dl_utils import Listener as InstaListener
from bot.utils.log_utils import group_logger, log, logger
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
            if not (is_supported(url) or is_valid_instagram_url(url)):
                continue
            supported_links.append(url)
        if not supported_links:
            return
        job = list(supported_links)
        t_args = extract_bracketed_prefix(text)
        while job:
            try:
                listener = DummyListener(job[0])
                if is_valid_instagram_url(listener.link):
                    if await insta_reply(event, listener.link, t_args):
                        job.pop(0)
                        continue
                audio = False
                twi = False
                _format = "bv*[ext=mp4][vcodec~='h264|avc1'][filesize<100M][height<={0}]+ba[ext=m4a]/b[ext=mp4][vcodec~='h264|avc1'][filesize<100M][height<={0}] / bv*+ba/b"
                _alt_format = "bv*[ext=mp4][vcodec~='h264|avc1'][height<={0}]+ba/b[ext=mp4][vcodec~='h264|avc1'][height<={0}] / bv*+ba/b"
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
                if result.get("extractor").casefold() == "twitter":
                    twi = True
                status_msg = await event.reply("*Downloading…*")
                await ytdl.add_download(
                    f"ytdl/{event.chat.id}:{event.id}",
                    _format.format(quality),
                    playlist,
                    status_msg,
                    trim_args=t_args,
                    twi=twi,
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


async def insta_reply(event, link, t_args=None) -> bool:
    listener = InstaListener(link)
    insta_dl = InstagramDLHelper(listener)
    status_msg = await event.reply("*Downloading…*")
    downloads = await insta_dl.add_download(
        f"insta_dl/{event.chat.id}:{event.id}",
        message=status_msg,
        trim_args=t_args,
    )
    if not (insta_dl.download_is_complete or downloads):
        if listener.is_cancelled and listener.error:
            await status_msg.edit("*Download Failed;* Trying fallback...")
        await insta_dl.clean_up()
        s_remove(insta_dl.folder, folders=True)
        return
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

        if file.media_type != "image":
            await event.reply_video(file_name, wrap_lines_with_asterisks(file.caption))
        else:
            await event.reply_photo(file_name, wrap_lines_with_asterisks(file.caption))
    await insta_dl.clean_up()
    s_remove(insta_dl.folder, folders=True)
    await status_msg.delete() if not insta_dl._listener.is_cancelled else None
    return True
