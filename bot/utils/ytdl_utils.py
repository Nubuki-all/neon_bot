import asyncio
import json
import math
import shutil
import time
import uuid
from os import listdir
from os import path as ospath
from re import search as re_search
from secrets import token_urlsafe

from yt_dlp import DownloadError, YoutubeDL, extractor
from yt_dlp.utils import download_range_func

from bot.config import bot, conf
from bot.fun.emojis import enhearts

from .bot_utils import (
    hbs,
    is_valid_video_timestamp,
    sync_to_async,
    time_formatter,
    value_check,
    video_timestamp_to_seconds,
)
from .log_utils import log
from .msg_utils import user_is_admin, user_is_privileged
from .os_utils import enshell, s_remove

# Ripped almost all the code from;
# https://github.com/anasty17/mirror-leech-telegram-bot/blob/master/bot/helper/mirror_leech_utils/download_utils/yt_dlp_download.py


def is_supported(url):
    extractors = extractor.gen_extractors()
    for e in extractors:
        if e.suitable(url) and e.IE_NAME != "generic":
            return True
    return False


def get_video_name(base_name, with_quality=False):
    try:
        if not base_name.split()[-1].isdigit():
            return base_name
        index = base_name.rfind(" ")
        base_name = base_name[:index]
        if with_quality or len(base_name.split()) < 2:
            return
        if base_name.split()[-1].endswith("fps") or (
            base_name.split()[-1].endswith("p") and base_name.split()[-1][:-1].isdigit()
        ):
            index = base_name.rfind(" ")
            base_name = base_name[:index]
            return
        return
    except Exception:
        return
    finally:
        return base_name.strip()


def extract_info(link, options={"cookiefile": ".cookies.txt", "ignoreerrors": True}):
    with YoutubeDL(options) as ydl:
        result = ydl.extract_info(link, download=False)
        if result is None:
            raise ValueError("Info result is None")
        return result


def is_valid_trim_args(args: str, total_dur: float | None = None) -> bool:
    s_args = args.split("-")
    if len(s_args) > 2:
        return False
    for x in s_args:
        if not (x.isdigit() or is_valid_video_timestamp(x)):
            return False
    st_, et_ = map(video_timestamp_to_seconds, s_args)
    if st_ >= et_:
        return False
    if total_dur and et_ > int(total_dur):
        return False
    return True


async def get_key_frames(path: str):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-skip_frame",
        "nokey",
        "-show_entries",
        "frame=pts_time",
        "-of",
        "csv=p=0",
        "-print_format",
        "json",
        path,
    ]
    process, stdout, stderr = await enshell(cmd)
    if process.returncode != 0:
        raise RuntimeError(
            # type: ignore
            f"stderr: {stderr} Return code: {process.returncode}"
        )
    j = json.loads(stdout)
    return [float(x["pts_time"]) for x in j["frames"]]


async def trim_vid(
    start_time: int, end_time: int, input_file: str, output_file: str, seek=False
):
    cmd = [
        "ffmpeg",
        "-i",
        input_file,
        "-ss",
        f"{start_time}",
        "-to",
        f"{end_time}",
        "-c",
        "copy",
        "-avoid_negative_ts",
        "1",
        output_file,
    ]
    alt_cmd = [
        "ffmpeg",
        "-ss",
        f"{start_time}",
        "-i",
        input_file,
        "-c",
        "copy",
        "-avoid_negative_ts",
        "1",
        output_file,
    ]
    if seek:
        cmd = alt_cmd
    process, stdout, stderr = await enshell(cmd)
    if process.returncode != 0:
        raise RuntimeError(
            # type: ignore
            f"stderr: {stderr} Return code: {process.returncode}"
        )


class DummyListener:
    def __init__(self, link):
        self.completed = False
        self.error = None
        self.is_cancelled = False
        self.link = link
        self.name = None
        self.size = 0


class MyLogger:
    def __init__(self, obj, listener):
        self._obj = obj
        self._listener = listener

    def debug(self, msg):
        # Hack to fix changing extension
        if not self._obj.is_playlist:
            if (
                match := re_search(r".Merger..Merging formats into..(.*?).$", msg)
                or re_search(r".ExtractAudio..Destination..(.*?)$", msg)
                or re_search(r".VideoConvertor..Converting video from..(.*?)$", msg)
            ):
                log(e=msg)
                newname = match.group(1)
                newname = newname.rsplit("/", 1)[-1]
                self._listener.name = newname

    @staticmethod
    def warning(msg):
        log(e=msg)

    @staticmethod
    def error(msg):
        if msg != "ERROR: Cancelling...":
            log(e=msg)


class YoutubeDLHelper:
    def __init__(self, listener):
        self._last_downloaded = 0
        self._progress = 0
        self._downloaded_bytes = 0
        self._download_speed = 0
        self._eta = "-"
        self._listener = listener
        self._gid = ""
        self._ext = ""
        self.is_playlist = False
        self.file_name = None
        self.start = None
        self.message = None
        self.re_encode = False
        self.unfin_str = "🤍"
        self.opts = {
            "progress_hooks": [self._on_download_progress],
            "logger": MyLogger(self, self._listener),
            "usenetrc": False,
            "cookiefile": ".cookies.txt",
            "allow_multiple_video_streams": True,
            "allow_multiple_audio_streams": True,
            "noprogress": True,
            "allow_playlist_files": True,
            "overwrites": True,
            "writethumbnail": True,
            "trim_file_name": 220,
            "retry_sleep_functions": {
                "http": lambda n: 3,
                "fragment": lambda n: 3,
                "file_access": lambda n: 3,
                "extractor": lambda n: 3,
            },
        }

    @property
    def download_speed(self):
        return self._download_speed

    @property
    def downloaded_bytes(self):
        return self._downloaded_bytes

    @property
    def download_is_complete(self):
        return self._listener.completed

    @property
    def size(self):
        return self._listener.size

    @property
    def name(self):
        return self._listener.name

    @property
    def progress(self):
        return self._progress

    @property
    def eta(self):
        return self._eta

    def _on_download_progress(self, d):
        if self._listener.is_cancelled:
            raise ValueError("Cancelling...")
        if d["status"] == "finished":
            if self.is_playlist:
                self._last_downloaded = 0
        elif d["status"] == "downloading":
            self._download_speed = d["speed"]
            if self.is_playlist:
                downloadedBytes = d["downloaded_bytes"]
                chunk_size = downloadedBytes - self._last_downloaded
                self._last_downloaded = downloadedBytes
                self._downloaded_bytes += chunk_size
            else:
                if d.get("total_bytes"):
                    self._listener.size = d["total_bytes"]
                elif d.get("total_bytes_estimate"):
                    self._listener.size = d["total_bytes_estimate"]
                self._downloaded_bytes = d["downloaded_bytes"]
                self._eta = d.get("eta")
            try:
                self._progress = (self._downloaded_bytes / self._listener.size) * 100
            except BaseException:
                pass

    async def _cancel(self, event, __, client):
        "Cancel a ytdl download."
        user = event.from_user.id
        if not user_is_privileged(user):
            group_info = await client.get_group_info(event.chat.jid)
            if not user_is_admin(user, group_info.Participants):
                return
        self._on_download_error(f"*Download with gid: {self._gid} has been cancelled!*")

    async def _on_download_start(self, from_queue=False):
        self.cancel_cmd = "cancel_" + self._gid
        self.start = time.time()
        bot.add_handler(self._cancel, self.cancel_cmd)
        self.c_message = await self.message.reply(conf.CMD_PREFIX + self.cancel_cmd)
        asyncio.create_task(self.progress_monitor())

    async def progress_monitor(self):
        while not self._listener.is_cancelled:
            if self.download_is_complete:
                break
            if self.size >= 100000000 and not self.is_playlist:
                self._listener.is_cancelled = True
                await self.message.edit(
                    f"*{self.name or 'Media'} too large to upload.*"
                )
                continue
            ud_type = "*Downloading*"
            ud_type += f":\n{self.name}" if self.name else "…"
            remaining_size = self.size - self.downloaded_bytes
            total = self.size
            current = self.downloaded_bytes
            speed = self.download_speed
            time_to_completion = self.eta
            now = time.time()
            diff = now - self.start
            fin_str = enhearts()

            progress = "\n{0}{1}\n*Progress:* {2}%\n".format(
                "".join([fin_str for i in range(math.floor(self.progress / 10))]),
                "".join(
                    [self.unfin_str for i in range(10 - math.floor(self.progress / 10))]
                ),
                round(self.progress, 2),
            )
            tmp = (
                progress
                + "*{0} of {1}*\n*Speed:* {2}/s\n*Remains:* {3}\n*ETA:* {4}\n*Elapsed:* {5}\n".format(
                    value_check(hbs(current)),
                    value_check(hbs(total)),
                    value_check(hbs(speed)),
                    value_check(hbs(remaining_size)),
                    # elapsed_time if elapsed_time != '' else "0 s",
                    # download.eta if len(str(download.eta)) < 30 else "0 s",
                    time_to_completion if time_to_completion else "0 s",
                    time_formatter(diff),
                )
            )
            dsp = "{}\n{}".format(ud_type, tmp)
            dsp += "\n*To cancel use the below command;*"
            await self.message.edit(dsp)
            await asyncio.sleep(5)
        await self.c_message.delete()
        bot.unregister(self.cancel_cmd)

    def _on_download_error(self, error):
        self._listener.is_cancelled = True
        self._listener.error = error
        s_remove(self.folder, folders=True)

    def _extract_meta_data(self):
        if self._listener.link.startswith(("rtmp", "mms", "rstp", "rtmps")):
            self.opts["external_downloader"] = "ffmpeg"
        with YoutubeDL(self.opts) as ydl:
            try:
                result = ydl.extract_info(self._listener.link, download=False)
                if result is None:
                    raise ValueError("Info result is None")
            except Exception as e:
                return self._on_download_error(str(e))
            if "entries" in result:
                for entry in result["entries"]:
                    if not entry:
                        continue
                    elif "filesize_approx" in entry:
                        self._listener.size += entry.get("filesize_approx", 0) or 0
                    elif "filesize" in entry:
                        self._listener.size += entry.get("filesize", 0) or 0
                    if not self._listener.name:
                        outtmpl_ = "%(series,playlist_title,channel)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d.%(ext)s"
                        self._listener.name, ext = ospath.splitext(
                            ydl.prepare_filename(entry, outtmpl=outtmpl_)
                        )
                        if not self._ext:
                            self._ext = ext
            else:
                outtmpl_ = "%(title,fulltitle,alt_title)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d%(episode_number&E|)s%(episode_number|)02d%(height& |)s%(height|)s%(height&p|)s%(fps|)s%(fps&fps|)s%(tbr& |)s%(tbr|)d.%(ext)s"
                if self._ext == ".mp3":
                    outtmpl_ = (
                        "%(title,fulltitle,alt_title)s • %(artist,uploader)s.%(ext)s"
                    )
                else:
                    h264_formats = [
                        fmt["format_id"]
                        for fmt in result["formats"]
                        if (
                            (
                                fmt.get("vcodec")
                                and fmt.get("vcodec", "").startswith("avc1")
                            )
                            or (
                                fmt.get("vcodec") == "h264"
                            )  # Handle both representations
                            and fmt.get("acodec") != "none"
                        )  # Exclude video-only formats
                    ]
                    if not h264_formats:
                        self.re_encode = True
                realName = ydl.prepare_filename(result, outtmpl=outtmpl_)
                ext = ospath.splitext(realName)[-1]
                self.file_name = (
                    f"{self._listener.name}{ext}" if self._listener.name else realName
                )
                self._listener.name = f"{uuid.uuid4()}{ext}"
                if not self._ext:
                    self._ext = ext

    def _download(self, path):
        try:
            with YoutubeDL(self.opts) as ydl:
                try:
                    ydl.download([self._listener.link])
                except DownloadError as e:
                    if not self._listener.is_cancelled:
                        self._on_download_error(str(e))
                    return
            if self.is_playlist and (
                not ospath.exists(path) or len(listdir(path)) == 0
            ):
                self._on_download_error(
                    "No video is available to be downloaded from this playlist. Check logs for more details"
                )
                return
            if self._listener.is_cancelled:
                return
            self._listener.completed = True
            # async_to_sync(self._listener.on_download_complete)
        except ValueError:
            pass
        except Exception:
            log(Exception)

    async def add_download(
        self,
        path,
        qual,
        playlist,
        message,
        options={},
        trim_args=None,
        twi=False,
    ):
        self.folder = path
        self.message = message
        if playlist:
            self.opts["ignoreerrors"] = True
            self.is_playlist = True

        self._gid = token_urlsafe(10)

        await self._on_download_start()

        self.opts["postprocessors"] = [
            {
                "add_chapters": True,
                "add_infojson": "if_exists",
                "add_metadata": True,
                "key": "FFmpegMetadata",
            }
        ]

        if qual.startswith("ba/b-"):
            audio_info = qual.split("-")
            qual = audio_info[0]
            audio_format = audio_info[1]
            rate = audio_info[2]
            self.opts["postprocessors"].append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                    "preferredquality": rate,
                }
            )
            if audio_format == "vorbis":
                self._ext = ".ogg"
            elif audio_format == "alac":
                self._ext = ".m4a"
            else:
                self._ext = f".{audio_format}"

        if trim_args and not twi:
            s_time, e_time = map(video_timestamp_to_seconds, trim_args.split("-"))
            self.opts["download_ranges"] = download_range_func(
                [], [[float(s_time), float(e_time)]]
            )
            self.opts["force_keyframes_at_cuts"] = True
            self.opts["format_sort"] = ["proto:https"]

        if options:
            self._set_options(options)

        self.opts["format"] = qual

        await sync_to_async(self._extract_meta_data)
        if self._listener.is_cancelled:
            return

        if not self._listener.name:
            self._on_download_error(
                "No video is available to be downloaded from this playlist. Check logs for more details"
            )
            return
        base_name, ext = ospath.splitext(self._listener.name)
        trim_name = self._listener.name if self.is_playlist else base_name
        if len(trim_name.encode()) > 200:
            self._listener.name = (
                self._listener.name[:200]
                if self.is_playlist
                else f"{base_name[:200]}{ext}"
            )
            base_name = ospath.splitext(self._listener.name)[0]

        if self.is_playlist:
            self.opts["outtmpl"] = {
                "default": f"{path}/{self._listener.name}/%(title,fulltitle,alt_title)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d%(episode_number&E|)s%(episode_number|)02d%(height& |)s%(height|)s%(height&p|)s%(fps|)s%(fps&fps|)s%(tbr& |)s%(tbr|)d.%(ext)s",
                # "thumbnail": f"{path}/yt-dlp-thumb/%(title,fulltitle,alt_title)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d%(episode_number&E|)s%(episode_number|)02d%(height& |)s%(height|)s%(height&p|)s%(fps|)s%(fps&fps|)s%(tbr& |)s%(tbr|)d.%(ext)s",
            }
        elif "download_ranges" in options:
            self.opts["outtmpl"] = {
                "default": f"{path}/{base_name}/%(section_number|)s%(section_number&.|)s%(section_title|)s%(section_title&-|)s%(title,fulltitle,alt_title)s %(section_start)s to %(section_end)s.%(ext)s",
                # "thumbnail": f"{path}/yt-dlp-thumb/%(section_number|)s%(section_number&.|)s%(section_title|)s%(section_title&-|)s%(title,fulltitle,alt_title)s %(section_start)s to %(section_end)s.%(ext)s",
            }
        elif any(
            key in options
            for key in [
                "writedescription",
                "writeinfojson",
                "writeannotations",
                "writedesktoplink",
                "writewebloclink",
                "writeurllink",
                "writesubtitles",
                "writeautomaticsub",
            ]
        ):
            self.opts["outtmpl"] = {
                "default": f"{path}/{base_name}/{self._listener.name}",
                "thumbnail": f"{path}/yt-dlp-thumb/{base_name}.%(ext)s",
            }
        else:
            self.opts["outtmpl"] = {
                "default": f"{path}/{self._listener.name}",
                "thumbnail": f"{path}/{base_name}.%(ext)s",
            }

        if qual.startswith("ba/b") and not self.is_playlist:
            self._listener.name = f"{base_name}{self._ext}"
        elif not (self.is_playlist or self._listener.name.endswith("mp4")):
            self.opts["postprocessors"].append(
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            )
            self._ext = ".mp4"
            self._listener.name = f"{base_name}{self._ext}"
        elif self.re_encode:
            self.opts["postprocessors"].append(
                {
                    "key": "FFmpegCopyStream",
                }
            )
            self.opts["postprocessor_args"] = {}
            self.opts["postprocessor_args"].update(
                copystream=["-c:v", "libx264", "-c:a", "copy"]
            )

        if self._ext in [
            ".mp3",
            ".mkv",
            ".mka",
            ".ogg",
            ".opus",
            ".flac",
            ".m4a",
            # ".mp4",
            ".mov",
            ".m4v",
        ]:
            self.opts["postprocessors"].append(
                {
                    "already_have_thumbnail": True,
                    "key": "EmbedThumbnail",
                }
            )

        # msg, button = await stop_duplicate_check(self._listener)
        # if msg:
        # await self._listener.on_download_error(msg, button)
        # return

        # add_to_queue, event = await check_running_tasks(self._listener)
        # if add_to_queue:
        # LOGGER.info(f"Added to Queue/Download: {self._listener.name}")
        # async with task_dict_lock:
        # task_dict[self._listener.mid] = QueueStatus(
        # self._listener, self._gid, "dl"
        # )
        # await event.wait()
        # if self._listener.is_cancelled:
        # return
        # LOGGER.info(f"Start Queued Download from YT_DLP: {self._listener.name}")
        # await self._on_download_start(True)

        # if not add_to_queue:
        log(e=f"Downloading with YT_DLP: {self.file_name or self._listener.name}")

        await sync_to_async(self._download, path)
        self.base_name = ospath.splitext(self.file_name or self._listener.name)[0]

        """
        if not qual.startswith("ba/b"):
            self._listener.name = f"{base_name}{self._ext}"
        """
        if trim_args and twi:
            start_time, end_time = map(video_timestamp_to_seconds, trim_args.split("-"))

            file = f"{self.folder}/{self.name}"
            k_f = await get_key_frames(file)
            for x in reversed(k_f):
                if x <= start_time:
                    seek_time = x
                    break

            start_time = start_time - seek_time if seek_time != start_time else 0
            log(e=seek_time)
            tmp_file = f"{self.folder}/temp.{self._ext}"
            tmp_file2 = f"{self.folder}/temp2.{self._ext}"
            await trim_vid(seek_time, end_time, file, tmp_file, seek=True)
            await trim_vid(seek_time, end_time, tmp_file, tmp_file2)
            shutil.copy2(tmp_file2, file)
            s_remove(tmp_file)
            s_remove(tmp_file2)

    async def cancel_task(self):
        self._listener.is_cancelled = True
        log(e=f"Cancelling ytdlp Download: {self._listener.name}")
        self._on_download_error("Stopped by User!")

    def _set_options(self, options):
        options = options.split("|")
        for opt in options:
            key, value = map(str.strip, opt.split(":", 1))
            if value.startswith("^"):
                if "." in value or value == "^inf":
                    value = float(value.split("^", 1)[1])
                else:
                    value = int(value.split("^", 1)[1])
            elif value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value.startswith(("{", "[", "(")) and value.endswith(("}", "]", ")")):
                value = eval(value)

            if key == "postprocessors":
                if isinstance(value, list):
                    self.opts[key].extend(tuple(value))
                elif isinstance(value, dict):
                    self.opts[key].append(value)
            elif key == "download_ranges":
                if isinstance(value, list):
                    self.opts[key] = lambda info, ytdl: value
            else:
                self.opts[key] = value
