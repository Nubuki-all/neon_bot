import asyncio
import json
import datetime
import itertools
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
from urllib.parse import urlparse, urlunparse

import aiohttp
import httpx
import pytz
import requests
from ffmpeg.asyncio import FFmpeg

from bot import LOGS, bot, telegraph_errors, time

THREADPOOL = ThreadPoolExecutor(max_workers=1000)
http = httpx.AsyncClient(http2=True)


def gfn(fn):
    "gets module path"
    return ".".join([fn.__module__, fn.__qualname__])


async def sync_to_async(func, *args, wait=True, **kwargs):
    pfunc = partial(func, *args, **kwargs)
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(THREADPOOL, pfunc)
    return await future if wait else future


def create_api_token(retries=10):
    telgrph_tkn_err_msg = "Couldn't not successfully create telegraph api token!."
    while retries:
        try:
            bot.tgp_client.create_api_token("Rss")
            break
        except (requests.exceptions.ConnectionError, ConnectionError) as e:
            retries -= 1
            if not retries:
                LOGS.info(telgrph_tkn_err_msg)
                break
            time.sleep(1)
    return retries


async def post_to_tgph(title, text, author: str = None, author_url: str = None):
    bot.author = (await bot.client.get_me()).PushName if not bot.author else bot.author
    retries = 10
    while retries:
        try:
            page = await sync_to_async(
                bot.tgp_client.post,
                title=title,
                author=(author or bot.author),
                author_url=(author_url or bot.author_url),
                text=text,
            )
            return page
        except telegraph_errors.APITokenRequiredError as e:
            result = await sync_to_async(create_api_token)
            if not result:
                raise e
        except (requests.exceptions.ConnectionError, ConnectionError) as e:
            retries -= 1
            if not retries:
                raise e
            await asyncio.sleep(1)


def list_to_str(lst: list, sep=" ", start: int = None, md=True):
    string = ""
    t_start = start if isinstance(start, int) else 1
    for i, count in zip(lst, itertools.count(t_start)):
        if start is None:
            string += str(i) + sep
            continue
        entry = f"`{i}`"
        string += f"{count}. {entry} {sep}"

    return string.rstrip(sep)


def split_text(text: str, split="\n", pre=False, list_size=4000):
    current_list = ""
    message_list = []
    for string in text.split(split):
        line = string + split if not pre else split + string
        if len(current_list) + len(line) <= list_size:
            current_list += line
        else:
            # Add current_list to account_list
            message_list.append(current_list)
            # Reset the current_list with a new "line".
            current_list = line
    # Add the last line into list.
    message_list.append(current_list)
    return message_list


async def get_json(link):
    async with aiohttp.ClientSession() as requests:
        result = await requests.get(link)
        return await result.json()


async def get_text(link):
    async with aiohttp.ClientSession() as requests:
        result = await requests.get(link)
        return await result.text()


tz = pytz.timezone("Africa/Lagos")


def get_timestamp(date: str):
    return (
        datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
        .replace(tzinfo=tz)
        .timestamp()
    )


def get_date_from_ts(timestamp):
    try:
        date = datetime.datetime.fromtimestamp(timestamp, tz)
        return date.strftime("%d %b %Y %I:%M %p")
    except Exception:
        return 0


def get_date_from_isostr(iso_str):
    if iso_str.endswith("Z"):
        iso_str = iso_str.replace("Z", "+00:00")

    try:
        dt_object = datetime.datetime.fromisoformat(iso_str)
    except ValueError:
        dt_object = datetime.datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S%z")

    return dt_object.strftime("%Y-%m-%d %I:%M %p %Z")


def time_formatter(seconds: float) -> str:
    """humanize time"""
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        ((str(days) + "d, ") if days else "")
        + ((str(hours) + "h, ") if hours else "")
        + ((str(minutes) + "m, ") if minutes else "")
        + ((str(seconds) + "s, ") if seconds else "")
    )
    return tmp[:-2]


def value_check(value):
    if not value:
        return "-"
    return value


def hbs(size: int):
    if not size:
        return ""
    power = 2**10
    raised_to_pow = 0
    dict_power_n = {0: "B", 1: "K", 2: "M", 3: "G", 4: "T", 5: "P"}
    while size > power:
        size /= power
        raised_to_pow += 1
    return str(round(size, 2)) + " " + dict_power_n[raised_to_pow] + "B"


def human_format_num(num):
    num = float("{:.3g}".format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return "{}{}".format(
        "{:f}".format(num).rstrip("0").rstrip("."), ["", "K", "M", "B", "T"][magnitude]
    )


def is_video_file(filename: str):
    video_file_extensions = (
        ".3g2",
        ".3gp",
        ".3gp2",
        ".3gpp",
        ".avc",
        ".avd",
        ".avi",
        ".evo",
        ".fli",
        ".flv",
        ".flx",
        ".m4u",
        ".m4v",
        ".mkv",
        ".mov",
        ".movie",
        ".mp21",
        ".mp21",
        ".mp2v",
        ".mp4",
        ".mp4v",
        ".mpeg",
        ".mpeg1",
        ".mpeg4",
        ".mpf",
        ".mpg",
        ".mpg2",
        ".xvid",
    )
    if filename.endswith((video_file_extensions)):
        return True


async def png_to_jpg(png: bytes | str):
    raw = False if isinstance(png, str) else True
    ffmpeg = (
        FFmpeg()
        .option("y")
        .input("pipe:0" if raw else png)
        .output(
            "pipe:1",
            f="mjpeg",
        )
    )
    input_ = png if raw else None
    return await ffmpeg.execute(input_)


def turn(turn_id: str = None):
    if turn_id:
        return turn_id in bot.p_queue
    return bot.p_queue


async def wait_for_turn(turn_id: str):
    while turn(turn_id):
        await asyncio.sleep(5)
        if bot.p_queue[0] == turn_id:
            return 1


def waiting_for_turn():
    return turn() and len(turn()) > 1


async def shutdown_services():
    await bot.client.disconnect()
    await bot.requests.close()
    bot.stop_back_up = True
    await bot.backup_wa_db()
    if bot.pending_saved_messages:
        if not bot.auto_save_msg_is_running:
            return
        bot.msg_leaderboard_counter = 100
        bot.force_save_messages = True
        while bot.pending_saved_messages:
            await asyncio.sleep(1)


def same_month(date, day_offset: int = 1, hour_offset: int = 0):
    """returns true if datetime object is part of the current month"""
    d1 = date
    d2 = datetime.datetime.today() + datetime.timedelta(
        days=day_offset, hours=hour_offset
    )
    return d1.month == d2.month and d1.year == d2.year


def same_week(date, day_offset: int = 1, hour_offset: int = 0):
    """returns true if datetime object is part of the current week"""
    d1 = date
    d2 = datetime.datetime.today() + datetime.timedelta(
        days=day_offset, hours=hour_offset
    )
    return d1.isocalendar()[1] == d2.isocalendar()[1] and d1.year == d2.year


def get_sha256(string: str):
    return sha256(string.encode("utf-8")).hexdigest()


def trunc_string(string: str, limit: int):
    return (string[: limit - 2] + "…") if len(string) > limit else string


async def screenshot_page(target_url: str):
    """
    Generate screenshot from a url.
    From https://github.com/AmanoTeam/EduuRobot/blob/df2cb53bc9453b08267c9885fabf6c61355a0fc3/eduu/plugins/prints.py#L81
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:108.0) Gecko/20100101 Firefox/108.0",
    }
    data = {
        "url": target_url,
        # Sending a random CSS to make the API to generate a new screenshot.
        "css": f"random-tag: {uuid.uuid4()}",
        "render_when_ready": False,
        "viewport_width": 1280,
        "viewport_height": 720,
        "device_scale": 2,
    }
    try:
        resp = await http.post(
            "https://htmlcsstoimage.com/demo_run", headers=headers, json=data
        )
        return resp.json()["url"]
    except (JSONDecodeError, KeyError) as e:
        raise Exception("Screenshot API returned an invalid response.") from e
    except HTTPError as e:
        raise Exception("Screenshot API seems offline. Try again later.") from e


def video_timestamp_to_seconds(timestamp: str) -> int:
    parts = list(map(int, timestamp.split(":")))
    parts.reverse()
    total_seconds = 0
    for i, part in enumerate(parts):
        total_seconds += part * (60**i)
    return total_seconds


def is_valid_video_timestamp(s: str) -> bool:
    """
    Checks if the string matches the format (e.g., "01:20:30", "20:30", "30")
    """
    if not re.fullmatch(r"^\d{1,2}(:\d{1,2}){0,2}$", s):
        return False

    # Step 2: Split into parts and convert to integers
    parts = list(map(int, s.split(":")))

    # Step 3: Validate numeric ranges
    # Seconds (last part) must be 0-59
    if parts[-1] < 0 or parts[-1] > 59:
        return False

    # Minutes (if present) must be 0-59
    if len(parts) >= 2 and (parts[-2] < 0 or parts[-2] > 59):
        return False

    # Hours (if present) must be >=0 (no upper limit)
    if len(parts) == 3 and parts[0] < 0:
        return False

    return True


async def read_binary(file):
    def stdlib_read(file):
        with open(file, "rb") as f:
            return f.read()

    return await sync_to_async(stdlib_read, file)


async def write_binary(file, bytes_):
    def stdlib_write(file, bytes_):
        with open(file, "wb") as f:
            f.write(bytes_)

    return await sync_to_async(stdlib_write, file, bytes_)


def ensure_default_db(uri: str, default_db: str) -> str:
    """
    If `uri` has no path component (i.e. no '/dbname' after the hosts),
    inject '/<default_db>' before any query string. Otherwise leave it alone.
    """
    parsed = urlparse(uri)
    # parsed.path will be '' or '/' if no db is present
    if parsed.path not in (None, "", "/"):
        return uri

    # build a new path
    new_path = "/" + default_db

    # reassemble the URI with the new path
    rebuilt = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            new_path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
    return rebuilt


def clean_whatsapp_md(text: str) -> str:
    """
    Remove WhatsApp Markdown markers:
      *bold*       → bold
      _italic_     → italic
      ~strike~     → strike
      ```code```   → code
      `monospace`  → monospace
    """
    # 1) Triple‑backtick blocks (multiline monospace)
    text = re.sub(r"```(.*?)```", r"\1", text, flags=re.DOTALL)
    # 2) Single‑backtick monospace
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 3) Bold
    text = re.sub(r"\*([^\*]+)\*", r"\1", text)
    # 4) Italic
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # 5) Strikethrough
    text = re.sub(r"~([^~]+)~", r"\1", text)
    return text


async def _run(*args: str) -> tuple[bytes, bytes, int]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return stdout, stderr, proc.returncode


async def probe_video(path: str) -> dict:
    stdout, _, rc = await _run(
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        path,
    )
    if rc != 0:
        raise RuntimeError(f"ffprobe failed on {path}")
    return json.loads(stdout)


async def check_moov_position(path: str) -> bool:
    """True = moov before mdat (faststart OK)."""
    _, stderr, _ = await _run("ffprobe", "-v", "trace", "-i", path)
    text = stderr.decode()
    moov_pos = text.find("'moov'")
    mdat_pos = text.find("'mdat'")
    if moov_pos == -1 or mdat_pos == -1:
        return False
    return moov_pos < mdat_pos


async def check_container_clean(path: str) -> bool:
    """True = no UDTA/container parse warnings."""
    _, stderr, _ = await _run("ffprobe", "-v", "warning", "-i", path)
    warn = stderr.decode()
    return "UDTA parsing failed" not in warn and "moov atom not found" not in warn


def _get_video_stream(info: dict) -> dict | None:
    return next((s for s in info["streams"] if s["codec_type"] == "video"), None)


def _get_audio_stream(info: dict) -> dict | None:
    return next((s for s in info["streams"] if s["codec_type"] == "audio"), None)


async def needs_normalization(info: dict, path: str) -> list[str]:
    issues = []

    # Run container checks concurrently
    faststart, container_clean = await asyncio.gather(
        check_moov_position(path),
        check_container_clean(path),
    )

    if not faststart:
        issues.append("moov atom at end of file")
    if not container_clean:
        issues.append("container has parse warnings (UDTA/moov corruption)")

    video = _get_video_stream(info)
    if video:
        bitrate_kbps = int(video.get("bit_rate", 0)) // 1000
        codec = video.get("codec_name", "")
        fps_str = video.get("r_frame_rate", "0/1")
        num, den = map(int, fps_str.split("/"))
        fps = num / den if den else 0

        if fps > 60.5:
            issues.append(f"fps={fps:.2f} (above 60fps HD limit)")
        if bitrate_kbps > 20000:
            issues.append(f"video bitrate={bitrate_kbps} kbps (risk of mobile stutter)")
        if codec not in ("h264", "hevc"):
            issues.append(f"codec={codec} (WhatsApp expects H.264 or HEVC)")

    audio = _get_audio_stream(info)
    if audio:
        sample_rate = int(audio.get("sample_rate", 0))
        if sample_rate not in (44100, 48000):
            issues.append(f"audio sample rate={sample_rate} Hz (use 44100 or 48000)")

    return issues


async def normalize_for_whatsapp(input_path: str, output_path: str, transcode: bool = False):
    video = _get_video_stream(await probe_video(input_path))
    codec = video.get("codec_name", "h264") if video else "h264"

    if not transcode:
        # Remux only
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-c", "copy",
            "-movflags", "+faststart",
            "-map_metadata", "-1",
            output_path,
        ]
    elif codec == "hevc":
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", "libx265",
            "-preset", "fast",
            "-crf", "28",
            "-maxrate", "8000k",
            "-bufsize", "16000k",
            "-tag:v", "hvc1", 
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-map_metadata", "-1",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", "libx264",
            "-crf", "23",
            "-maxrate", "8000k",
            "-bufsize", "16000k",
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-map_metadata", "-1",
            output_path,
        ]

    _, stderr, rc = await _run(*cmd)
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode()}")
