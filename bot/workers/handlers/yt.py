import asyncio
import os

from clean_links.clean import clean_url
from urlextract import URLExtract

from bot.config import bot
from bot.utils.bot_utils import png_to_jpg, sync_to_async
from bot.utils.log_utils import logger
from bot.utils.msg_utils import chat_is_allowed, extract_bracketed_prefix
from bot.utils.os_utils import dir_exists, file_exists, s_remove, size_of
from bot.utils.ytdl_utils import (
    DummyListener,
    YoutubeDLHelper,
    extract_info,
    get_video_name,
    is_supported,
    is_valid_trim_args,
)


async def folder_upload(folder, event, status_msg, audio):
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
            base_name = get_video_name(os.path.splitext(name)[0])
            file = os.path.join(path, name)
            await status_msg.edit(f"[{t}/{i}]\nUploading *{name}*…")
            if size_of(file) >= 100000000:
                await event.reply(f"*{name} too large to upload.*")
                await asyncio.sleep(3)
                continue

            if file.endswith(("png", "jpg", "jpeg")):
                event = await event.reply_photo(file, f"*{base_name}*")
            elif audio and file.endswith("mp3"):
                event = await event.reply_audio(file)
                await event.reply(f"*{base_name}*")
            elif file.endswith("mp4"):
                event = await event.reply_video(file, f"*{base_name}*")
            await asyncio.sleep(3)
            t += 1


async def youtube_reply(event, args, client):
    """
    Download and upload sent video from sent YouTube link
    """
    try:
        if not event.text:
            return
        if "#no_ytdl" in event.text:
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
            if not is_supported(url):
                continue
            supported_links.append(url)
        if not supported_links:
            return
        job = list(supported_links)
        while job:
            try:
                audio = False
                t_args = None
                twi = False
                _format = "bv*[ext=mp4][vcodec~='h264|avc1'][filesize<100M][height<={0}]+ba[ext=m4a]/b[ext=mp4][vcodec~='h264|avc1'][filesize<100M][height<={0}] / bv*+ba/b"
                _alt_format = "bv*[ext=mp4][vcodec~='h264|avc1'][height<={0}]+ba/b[ext=mp4][vcodec~='h264|avc1'][height<={0}] / bv*+ba/b"
                listener = DummyListener(job[0])
                ytdl = YoutubeDLHelper(listener)
                if "music" in listener.link:
                    audio = True
                    _format = "ba/b-mp3{0}"
                    quality = "-"
                elif "shorts" in listener.link and "(720p)" in text:
                    quality = "1280"
                else:
                    for qua in ["480", "360", "270", "240", "144"]:
                        if f"({qua}p)" in text:
                            quality = qua
                            break
                    else:
                        quality = "720"
                try:
                    result = await sync_to_async(extract_info, listener.link)
                except Exception:
                    await logger(Exception)
                    await asyncio.sleep(1)
                    job.pop(0)
                    continue
                playlist = "entries" in result
                if not (trimmed or audio or playlist) and (
                    t_args := extract_bracketed_prefix(text)
                ):
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
                        s_remove(ytdl.folder, folders=True)
                        job.pop(0)
                        continue
                    await logger(e=f"Uploading {file}…")
                    base_name = get_video_name(ytdl.base_name)
                    if not audio:
                        await event.reply_video(file, f"*{base_name}*")
                    else:
                        image = file[:-3] + "webp"
                        if not file_exists(image):
                            image = file[:-3] + "jpg"
                        with open(image, "rb") as pfile:
                            webp = pfile.read()
                        photo = await png_to_jpg(webp)
                        reply = await event.reply_photo(photo, f"*{base_name}*")
                        await reply.reply_audio(file)
                else:
                    await folder_upload(ytdl.folder, event, status_msg, audio)
                s_remove(ytdl.folder, folders=True)
                await status_msg.delete()
                job.pop(0)
            except Exception:
                await logger(Exception)
                job.pop(0)
    except Exception:
        await logger(Exception)
        await event.react("❌")
