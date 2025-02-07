import asyncio
import os

from clean_links.clean import clean_url
from urlextract import URLExtract

from bot.utils.bot_utils import sync_to_async
from bot.utils.log_utils import logger
from bot.utils.os_utils import dir_exists, file_exists, s_remove
from bot.utils.ytdl_utils import (
    DummyListener,
    YoutubeDLHelper,
    extract_info,
    is_supported,
)


async def folder_upload(folder, event, status_msg, audio):
    if not dir_exists(folder):
        return
    for path, subdirs, files in os.walk(file):
        subdirs.sort()
        if not files:
            if not os.listdir(path):
                continue
        i = len(files)
        t = 1
        for name in sorted(files):
            base_name = os.path.splitext(name)[0]
            file = os.path.join(path, name)
            await status_msg.edit(f"[{t}/{i}]\nUploading *{name}*…")
            if size_of(file) >= 100000000:
                await event.reply(f"*{name} too large to upload.*")
                continue

            if audio:
                event = await event.reply_audio(file)
            else:
                event = await event.reply_video(file, f"*{base_name}*")
            await asyncio.sleep(3)
            t += 1


async def youtube_reply(event, args, client):
    """
    Download and upload sent video from sent YouTube link
    """
    try:
        if event.type != "text":
            return
        extractor = URLExtract()
        urls = extractor.find_urls(event.text)
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
                listener = DummyListener(job[0])
                ytdl = YoutubeDLHelper(listener)
                if music in listener.link:
                    audio = True
                    form = "ba/b-{frmt}-"
                else:
                    audio = False
                    form = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b"
                try:
                    result = await sync_to_async(extract_info, listener.link)
                except Exception:
                    await logger(Exception)
                    await asyncio.sleep(1)
                    job.pop(0)
                    continue
                playlist = "entries" in result
                status_msg = await event.reply("*Downloading…*")
                await ytdl.add_download(
                    f"ytdl/{event.chat.id}:{event.id}",
                    form,
                    playlist,
                    status_msg,
                )
                if not ytdl.download_is_complete:
                    if listener.is_cancelled and listener.error:
                        await event.reply(listener.error)
                    job.pop(0)
                    s_remove(ytdl.folder, folders=True)
                    continue
                await status_msg.edit("Download completed, Now uploading…")
                file = f"{ytdl.folder}/{ytdl.name}"
                if not file_exists(file):
                    raise Exception(f"File: {file} not found!")
                await logger(e=f"Uploading {file}…")
                if not playlist:
                    await event.reply_video(file, f"*{ytdl.base_name}*") if not audio else await event.reply_audio(file)
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
        await event.react()
