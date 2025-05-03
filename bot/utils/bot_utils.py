import asyncio
import datetime
import itertools
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256

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
    parts = list(map(int, timestamp.split(':')))
    parts.reverse()
    total_seconds = 0
    for i, part in enumerate(parts):
        total_seconds += part * (60 ** i)
    return total_seconds

def is_valid_video_timestamp(s: str) -> bool:
    """
    Checks if the string matches the format (e.g., "01:20:30", "20:30", "30")
    """
    if not re.fullmatch(r'^\d{1,2}(:\d{1,2}){0,2}$', s):
        return False
    
    # Step 2: Split into parts and convert to integers
    parts = list(map(int, s.split(':')))
    
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