from clean_links.clean import clean_url
from urlextract import URLExtract

from bot.config import bot
from bot.utils.log_utils import logger
from bot.utils.ytdl_utils import DummyListener, YoutubeDLHelper, extract_info, is_supported

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
                try:
                    result = await sync_to_async(extract_info, self.link, options)
                except Exception as e:
                    await logger(Exception)
                    await asyncio.sleep(1)
                    job.pop(0)
                    continue
                playlist = "entries" in result
                status_msg = await event.reply("*Downloading…*")
                await ytdl.add_download("ytdl", "bv*[height<=1080]+ba/b[height<=1080] / wv*+ba/w", playlist, {}, status_msg)
                if not ytdl.download_is_complete:
                    if listener.is_cancelled:
                        await event.reply(listener.error)
                    job.pop(0)
                    continue
                await status_msg.edit("Download completed, Now uploading…")
                await event.reply_video("ytdl/"+ytdl.name, ytdl.name)
                await status_msg.delete()
            except Exception:
                await logger(Exception)
                job.pop(0)
    except Exception:
        await logger(Exception)
        await event.react()
