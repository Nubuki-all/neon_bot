import asyncio
import json
import math
import os
import secrets
import shutil
import time
from dataclasses import dataclass
from typing import Optional

from bot.config import bot, conf
from bot.fun.emojis import enhearts
from bot.pkgs.insta_dl import download_instagram
from bot.pkgs.pinterest_dl import download_pinterest
from bot.pkgs.tiktok_dl import download_tiktok

from .bot_utils import (
    hbs,
    is_valid_video_timestamp,
    time_formatter,
    value_check,
    video_timestamp_to_seconds,
)
from .log_utils import log
from .msg_utils import user_is_admin, user_is_privileged
from .os_utils import enshell, s_remove


@dataclass
class Listener:
    link: str = ""
    completed: bool = False
    error: Optional[str] = None
    is_cancelled: bool = False
    name: Optional[str] = None
    size: int = 0
    user_cancelled: bool = False
    is_insta: bool = False
    is_pintrest: bool = False
    is_tiktok: bool = False


class MediaHelper:
    """Handles download progress, cancellation, and trimming for Instagram & Pinterest."""

    def __init__(self, listener: Listener):
        self._listener = listener
        self._gid = ""
        self._downloaded_bytes = 0
        self._download_speed = 0
        self._eta = "-"
        self._start_time = 0
        self.c_message = None
        self._message = None
        self.cancel_cmd = None
        self.cleaned = False
        self.caption = ""
        self.ext = ""
        self.folder = ""
        self._progress_task: Optional[asyncio.Task] = None

    @property
    def download_speed(self):
        return self._download_speed

    @property
    def downloaded_bytes(self):
        return self._downloaded_bytes

    @property
    def progress(self):
        if self._listener.size == 0:
            return 0
        return (self._downloaded_bytes / self._listener.size) * 100

    @property
    def eta(self):
        return self._eta

    @property
    def name(self):
        return self._listener.name

    @property
    def download_is_complete(self):
        return self._listener.completed

    async def _on_download_progress(self, current: int, total: int, file_path: str):
        if self._listener.is_cancelled:
            raise ValueError("Cancelling...")

        self._listener.size = total
        self._downloaded_bytes = current
        elapsed = time.time() - self._start_time if self._start_time else 1
        if elapsed > 0:
            self._download_speed = current / elapsed
            if self._download_speed > 0:
                remaining = total - current
                self._eta = time_formatter(int(remaining / self._download_speed))
            else:
                self._eta = "-"
        else:
            self._download_speed = 0
        self._listener.name = file_path.split("/")[-1]

    async def _progress_loop(self):
        while not self._listener.is_cancelled:
            if self.download_is_complete:
                if self._message:
                    await self._update_message()
                break
            if self._message:
                await self._update_message()
            await asyncio.sleep(5)

    async def _update_message(self):
        fin_str = enhearts()
        prog = math.floor(self.progress / 10)
        bar = "".join([fin_str for _ in range(prog)]) + "".join(
            ["🤍" for _ in range(10 - prog)]
        )
        progress_line = f"\n{bar}\n*Progress:* {round(self.progress, 2)}%\n"
        info_line = (
            f"*{value_check(hbs(self._downloaded_bytes))} of {value_check(hbs(self._listener.size))}*\n"
            f"*Speed:* {value_check(hbs(self._download_speed))}/s\n"
            f"*ETA:* {self._eta}\n"
            f"*Elapsed:* {time_formatter(int(time.time() - self._start_time))}\n"
        )
        text = (
            f"*Downloading:* {self._listener.name or '...'}" + progress_line + info_line
        )
        await self._message.edit(text)

    async def _cancel(self, event, __, client):
        user = event.from_user.id
        if not user_is_privileged(user):
            group_info = await client.get_group_info(event.chat.jid)
            if not user_is_admin(user, group_info.Participants):
                return await event.react("🙅")
        await event.react("✅")
        self._listener.is_cancelled = True
        self._listener.user_cancelled = True
        self._on_download_error(f"Download with gid: {
            self._gid} was cancelled.")
        await self.clean_up()

    async def clean_up(self):
        if self.cleaned:
            return
        if self.cancel_cmd:
            bot.unregister(self.cancel_cmd)
        if self._progress_task and not self._progress_task.done():
            self._progress_task.cancel()
            try:
                await self._progress_task
            except asyncio.CancelledError:
                pass
            self._progress_task = None
        if self.c_message:
            try:
                await self.c_message.delete()
            except Exception:
                pass
        self.cleaned = True

    def _on_download_error(self, error: str):
        self._listener.is_cancelled = True
        self._listener.error = error
        log(e=error, error=True)
        s_remove(self.folder, folders=True)

    async def _get_key_frames(self, path: str):
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
            raise RuntimeError(f"ffprobe failed: {stderr}")
        j = json.loads(stdout)
        return [float(x["pts_time"]) for x in j["frames"]]

    async def _trim_video(
        self,
        start_time: float,
        end_time: float,
        input_file: str,
        output_file: str,
        seek: bool = False,
    ):
        if seek:
            cmd = [
                "ffmpeg",
                "-ss",
                f"{start_time}",
                "-i",
                input_file,
                "-to",
                f"{end_time}",
                "-c",
                "copy",
                "-avoid_negative_ts",
                "1",
                output_file,
            ]
        else:
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
        process, stdout, stderr = await enshell(cmd)
        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg trim failed: {stderr}")

    async def _apply_trim(self, file_path: str, trim_args: str):
        s_time_str, e_time_str = trim_args.split("-")
        for x in [s_time_str, e_time_str]:
            if not (x.isdigit() or is_valid_video_timestamp(x)):
                return False

        start_sec = video_timestamp_to_seconds(s_time_str)
        end_sec = video_timestamp_to_seconds(e_time_str)

        kfs = await self._get_key_frames(file_path)
        seek_time = next((x for x in reversed(kfs) if x <= start_sec), 0)

        base_dir = os.path.dirname(file_path)
        tmp1 = os.path.join(base_dir, "temp_trim1" + self.ext)
        tmp2 = os.path.join(base_dir, "temp_trim2" + self.ext)

        # First pass: seek to nearest keyframe, copy codec
        await self._trim_video(seek_time, end_sec, file_path, tmp1, seek=True)
        # Second pass: precise cut from seek_time (now a keyframe)
        await self._trim_video(start_sec, end_sec, tmp1, tmp2, seek=False)

        shutil.copy2(tmp2, file_path)
        s_remove(tmp1)
        s_remove(tmp2)

    async def _download(self, url: str, path: str):
        """Call the appropriate downloader based on the platform."""
        if self._listener.is_insta:
            return await download_instagram(
                url=url,
                output_dir=path,
                quiet=True,
                progress_callback=self._on_download_progress,
            )
        elif self._listener.is_tiktok:
            return await download_tiktok(
                url=url,
                output_dir=path,
                quiet=True,
                progress_callback=self._on_download_progress,
                cookie_file=".cookies.txt",
            )
        else:
            return await download_pinterest(
                url=url,
                output_dir=path,
                quiet=True,
                progress_callback=self._on_download_progress,
            )

    async def add_download(
        self,
        path: str,
        message=None,
        trim_args: Optional[str] = None,
    ):
        """
        Start an Instagram or Pinterest download.
        Registers a cancel command, downloads media, optionally trims videos.
        """
        self.folder = path
        self._message = message
        self._gid = secrets.token_urlsafe(10)
        self.cancel_cmd = f"cancel_{self._gid}"
        self._start_time = time.time()

        bot.add_handler(self._cancel, self.cancel_cmd)

        if message:
            self.c_message = await message.reply(
                conf.CMD_PREFIX + self.cancel_cmd,
            )
        self._progress_task = asyncio.create_task(self._progress_loop())

        try:
            results = await self._download(self._listener.link, path)
        except ValueError as e:
            if str(e) == "Cancelling...":
                self._on_download_error("Download cancelled by user.")
            else:
                self._on_download_error(str(e))
            await self.clean_up()
            return
        except Exception as e:
            self._on_download_error(str(e))
            await self.clean_up()
            return

        if self._listener.is_cancelled:
            await self.clean_up()
            s_remove(self.folder, folders=True)
            return

        if not results:
            self._on_download_error("No media returned.")
            await self.clean_up()
            return

        first_result = results[0]
        self._listener.name = os.path.basename(first_result.local_path)

        if trim_args and len(results) == 1 and first_result.media_type == "video":
            try:
                await self._apply_trim(first_result.local_path, trim_args)
            except Exception as e:
                self._on_download_error(f"Trimming failed: {e}")
                await self.clean_up()
                return

        self._listener.completed = True
        await self.clean_up()
        return results
