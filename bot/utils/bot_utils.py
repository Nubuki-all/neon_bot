import asyncio
import base64
import datetime
import io
import itertools
import json
import logging
import os
import re
import tempfile
import traceback
from collections import OrderedDict, deque
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from functools import partial
from hashlib import sha256
from urllib.parse import urlparse, urlunparse

import aiohttp
import pytz
import requests
import zendriver as zd
from ffmpeg.asyncio import FFmpeg
from PIL import Image, ImageChops

from bot import LOGS, bot, telegraph_errors, time
from bot.others.exceptions import NormalizeVidError

THREADPOOL = ThreadPoolExecutor(max_workers=1000)
_log_ = logging.getLogger(__name__)


def gfn(fn):
    "gets module path"
    return f"{fn.__module__}.{fn.__qualname__}"


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
        except (requests.exceptions.ConnectionError, ConnectionError):
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
        except telegraph_errors.APITokenRequiredError:
            result = await sync_to_async(create_api_token)
            if not result:
                raise
        except (requests.exceptions.ConnectionError, ConnectionError):
            retries -= 1
            if not retries:
                raise
            await asyncio.sleep(1)


def list_to_str(lst: list, sep=" ", start: int | None = None, md=True):
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
    num = float(f"{num:.3g}")
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return "{}{}".format(
        f"{num:f}".rstrip("0").rstrip("."), ["", "K", "M", "B", "T"][magnitude]
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
    if filename.endswith(video_file_extensions):
        return True


async def upscaled_png_to_jpg(png: bytes | str):
    raw = not isinstance(png, str)
    ffmpeg = (
        FFmpeg()
        .option("y")
        .input("pipe:0" if raw else png)
        .output(
            "pipe:1",
            f="mjpeg",
            # Caps width at 3840 and height at 2160, maintaining aspect ratio.
            vf="scale='min(3840,iw)':'-1':force_original_aspect_ratio=decrease",
        )
    )
    input_ = png if raw else None
    return await ffmpeg.execute(input_)


async def png_to_jpg(png: bytes | str):
    raw = not isinstance(png, str)
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


async def image_to_png(img: bytes | str):
    raw = not isinstance(img, str)
    ffmpeg = (
        FFmpeg()
        .option("y")
        .input("pipe:0" if raw else img)
        .output(
            "pipe:1",
            f="image2",
            vcodec="png",
        )
    )
    input_ = img if raw else None
    return await ffmpeg.execute(input_)


class TurnQueue:
    def __init__(self) -> None:
        self._queue: deque[str] = deque()
        # Fresh event every change so waiters can safely race with notifiers.
        self._changed = asyncio.Event()

    # --- notifications ----------------------------------------------------
    def _notify(self) -> None:
        old, self._changed = self._changed, asyncio.Event()
        old.set()

    # --- read API ---------------------------------------------------------
    def __contains__(self, turn_id: object) -> bool:
        return turn_id in self._queue

    def __len__(self) -> int:
        return len(self._queue)

    def __iter__(self) -> Iterator[str]:
        return iter(self._queue)

    def list(self) -> list[str]:
        return list(self._queue)

    @property
    def current(self) -> str | None:
        return self._queue[0] if self._queue else None

    @property
    def has_waiting(self) -> bool:
        """True if someone is queued behind the current turn."""
        return len(self._queue) > 1

    # --- write API --------------------------------------------------------
    def add(self, turn_id: str) -> bool:
        """Append to queue. Returns False if already present."""
        if turn_id in self._queue:
            return False
        self._queue.append(turn_id)
        self._notify()
        return True

    def remove(self, turn_id: str) -> bool:
        """Safely remove a turn (anywhere in the queue). Idempotent."""
        try:
            self._queue.remove(turn_id)
        except ValueError:
            return False
        self._notify()
        return True

    def advance(self) -> str | None:
        """Pop the front of the queue (turn is done). Returns the removed id."""
        if not self._queue:
            return None
        turn_id = self._queue.popleft()
        self._notify()
        return turn_id

    def clear(self) -> None:
        if not self._queue:
            return
        self._queue.clear()
        self._notify()

    # --- async wait -------------------------------------------------------
    async def wait_for_turn(self, turn_id: str) -> bool:
        """
        Block until `turn_id` is at the front of the queue.

        Returns True if it's now this turn's turn, False if the turn was
        removed (or queue cleared) before reaching the front.
        """
        while True:
            if not self._queue:
                return False
            if self._queue[0] == turn_id:
                return True
            if turn_id not in self._queue:
                return False

            # Snapshot the event AFTER the check. Because _notify swaps in a
            # new Event before setting the old one, we cannot miss an update:
            # either the condition is already false by the time we await, or
            # our snapshot will be set by the next change.
            event = self._changed
            if self._queue and self._queue[0] == turn_id:
                return True
            if turn_id not in self._queue and self._queue:
                return False
            await event.wait()


turn_queue = TurnQueue()


def turn(turn_id: str | None = None):
    if turn_id:
        return turn_id in turn_queue
    return turn_queue


async def wait_for_turn(turn_id: str) -> int:
    return await turn_queue.wait_for_turn(turn_id)


def waiting_for_turn() -> bool:
    return turn_queue.has_waiting


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
    return d1.isocalendar()[:2] == d2.isocalendar()[:2]


def get_sha256(string: str):
    return sha256(string.encode("utf-8")).hexdigest()


def trunc_string(string: str, limit: int):
    return (string[: limit - 2] + "…") if len(string) > limit else string


async def full_page_screenshot(page, output="fullpage.png"):
    full_height = await page.evaluate("document.body.scrollHeight")
    viewport_height = await page.evaluate("window.innerHeight")
    width = await page.evaluate(
        "Math.max(document.body.scrollWidth, document.documentElement.scrollWidth, window.innerWidth)"
    )
    dpr = await page.evaluate("window.devicePixelRatio") or 1

    if not full_height or not width or full_height < 10 or width < 10:
        await page.save_screenshot(output)
        return

    chunk_path = tempfile.mktemp(suffix=".png", prefix="chunk_")

    try:
        await page.evaluate("""
            window.__fixedEls = [];
            document.querySelectorAll('*').forEach(el => {
                const pos = window.getComputedStyle(el).position;
                if (pos === 'fixed' || pos === 'sticky') {
                    window.__fixedEls.push([el, el.style.visibility]);
                    el.style.visibility = 'hidden';
                }
            });
        """)

        img_width = int(width * dpr)
        img_height = int(full_height * dpr)
        stitched = Image.new("RGB", (img_width, img_height))
        offset = 0

        while offset < full_height:
            actual_scroll = min(offset, max(0, full_height - viewport_height))
            await page.evaluate(f"window.scrollTo(0, {actual_scroll})")
            await asyncio.sleep(0.3)
            await page.save_screenshot(chunk_path)
            chunk = Image.open(chunk_path)

            crop_top = int((offset - actual_scroll) * dpr)
            if crop_top > 0:
                chunk = chunk.crop((0, crop_top, chunk.width, chunk.height))

            stitched.paste(chunk, (0, int(offset * dpr)))
            offset += viewport_height

        await page.evaluate("""
            window.__fixedEls.forEach(([el, vis]) => el.style.visibility = vis);
        """)

        stitched.save(output)

    finally:
        if os.path.exists(chunk_path):
            os.remove(chunk_path)


def parse_netscape_cookies(file_path):
    cookies = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue

            fields = line.strip().split("\t")
            if len(fields) < 7:
                continue

            domain, _flag, path, secure, expiration, name, value = fields[:7]

            # Skip cookies with invalid names (e.g. starting with dot)
            if not name or name.startswith("."):
                continue

            cookie_dict = {
                "name": name,
                "value": value,
                "domain": domain if domain.startswith(".") else f".{domain}",
                "path": path,
                "secure": secure.upper() == "TRUE",
            }

            # Only include expires if it's a valid positive timestamp
            exp = int(expiration)
            if exp > 0:
                cookie_dict["expires"] = exp

            try:
                cdp_cookie = zd.cdp.network.CookieParam.from_json(cookie_dict)
                cookies.append(cdp_cookie)
            except Exception:
                continue

    return cookies


async def screenshot_page(
    url: str, full: bool = False, force_dark: bool = True, low_quality: bool = False
):
    """
    Generate screenshot from a url.
    """
    browser = None
    try:
        browser = await _start_browser(force_dark)
        page = await browser.get(url)
        await page
        await asyncio.sleep(5)
        path = tempfile.mktemp(suffix=".png", prefix="screenshot_")
        if full:
            try:
                await full_page_screenshot(page, path)
            except Exception:
                _log_.error(traceback.format_exc())
                await page.save_screenshot(path)
        else:
            await page.save_screenshot(path)
    finally:
        if browser:
            await _stop_browser(browser)
    output = await read_binary(path)
    return await png_to_jpg(output) if low_quality else output


async def _start_browser(force_dark: bool = True):
    """Start a headless browser with the shared cookies loaded."""
    b_args = [
        "--window-size=1920,1080",
        "--force-device-scale-factor=2",
        "--force-dark-mode",
    ]
    if not force_dark:
        b_args.pop(2)
    browser = await zd.start(headless=True, browser_args=b_args)
    try:
        if os.path.exists(".cookies.txt"):
            cookies = parse_netscape_cookies(".cookies.txt")
            for cookie in cookies:
                try:
                    await browser.cookies.set_all([cookie])
                except Exception as e:
                    _log_.warning(f"Failed to set cookie {cookie.name}: {e}")
    except Exception:
        await _stop_browser(browser)
        raise
    return browser


async def _stop_browser(browser):
    """Save the (possibly refreshed) cookies back, then stop the browser."""
    try:
        await save_cookies_txt(browser)
    except Exception:
        _log_.error(traceback.format_exc())
    try:
        await browser.stop()
    except Exception:
        _log_.error(traceback.format_exc())


# Per site:
#   hosts: hostnames the site is served from
#   open: JS run after load to show the comments (optional)
#   items: JS expression giving the top-level comment elements in page order
#   expand: JS function given a comment, opening its truncated text (optional)
COMMENT_SITES = {
    "youtube": {
        "hosts": ("youtube.com", "youtu.be"),
        "open": "document.querySelector('ytd-comments#comments')?.scrollIntoView()",
        "items": "document.querySelectorAll('ytd-comment-thread-renderer')",
        "expand": """
            el => el.querySelectorAll('#more').forEach(b => {
                if (b.offsetParent && !b.hidden) b.click();
            })
        """,
    },
    # Replies are tweets too: skip the post itself (it links to its own
    # status), ads (no timestamp) and the "Discover more" tweets after them.
    # "Show more" on a long reply opens its own page, so it isn't expanded.
    "x": {
        "hosts": ("x.com", "twitter.com"),
        "open": None,
        "items": """
            (() => {
                const id = (location.pathname.match(/status\\/(\\d+)/) || [])[1];
                const end = Array.from(
                    document.querySelectorAll("[data-testid='cellInnerDiv'] h2")
                ).find(h => /discover more/i.test(h.textContent));
                return Array.from(
                    document.querySelectorAll("article[data-testid='tweet']")
                ).filter(a =>
                    a.querySelector('time')
                    && !a.querySelector(`a[href*='/status/${id}'] time`)
                    && !(end && end.compareDocumentPosition(a)
                        & Node.DOCUMENT_POSITION_FOLLOWING)
                );
            })()
        """,
        "expand": None,
    },
}

LOGIN_WALL_MARKERS = (
    "/i/flow/login",
    "/login",
)


class CommentsUnavailable(Exception):
    pass


def _content_bbox(image, bg):
    """Bounding box of what differs from the background colour `bg`."""
    diff = ImageChops.difference(image, Image.new("RGB", image.size, bg))
    # Ignore near-background noise (anti-aliasing, faint separators)
    return diff.convert("L").point(lambda v: 255 if v > 16 else 0).getbbox()


def _is_blank(image):
    return not _content_bbox(image, image.getpixel((1, 1)))


def comment_site(url: str):
    """Return the COMMENT_SITES key for a URL, or None if unsupported."""
    host = (urlparse(url).hostname or "").lower()
    for site, conf in COMMENT_SITES.items():
        if any(host == h or host.endswith(f".{h}") for h in conf["hosts"]):
            return site


def _comments_url(site: str, url: str):
    # Shorts and youtu.be links don't show comments inline; use the watch page
    if site == "youtube":
        parsed = urlparse(url)
        video_id = None
        if parsed.hostname and parsed.hostname.endswith("youtu.be"):
            video_id = parsed.path.strip("/").split("/")[0]
        elif parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/")[2]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
    return url


async def _capture_region(page, x, y, width, height):
    """
    Capture a region given in page coordinates, a screen at a time.
    Capturing beyond the viewport resizes it, which makes X re-render
    (and drop) the tweets being captured, so every part is scrolled to.
    """
    view = await page.evaluate("window.innerHeight")
    parts = []
    top = y
    while top < y + height:
        part = min(view, y + height - top)
        await page.evaluate(f"window.scrollTo(0, {top})")
        await asyncio.sleep(0.3)
        data = await page.send(
            zd.cdp.page.capture_screenshot(
                format_="png",
                clip=zd.cdp.page.Viewport(
                    x=x, y=top, width=width, height=part, scale=1
                ),
                capture_beyond_viewport=False,
            )
        )
        parts.append(Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB"))
        top += part
    if len(parts) == 1:
        return parts[0]
    image = Image.new("RGB", (parts[0].width, sum(p.height for p in parts)))
    offset = 0
    for p in parts:
        image.paste(p, (0, offset))
        offset += p.height
    return image


# Long screenshots are sent in parts about this tall (in pixels), split
# between comments, so each part can be sent as soon as it's captured
COMMENTS_PART_HEIGHT = 4000


async def _stitch_comments(shots: list, low_quality: bool, min_width: int = 0):
    """
    Stack captured comments into one image, trimmed to the content but no
    narrower than `min_width`. Returns the image and its width.
    """
    width = max(s.width for s in shots)
    height = sum(s.height for s in shots)
    bg = shots[0].getpixel((1, 1))
    stitched = Image.new("RGB", (width, height), bg)
    y = 0
    for s in shots:
        stitched.paste(s, (0, y))
        y += s.height
    # Trim the empty space to the right of the comments
    bbox = _content_bbox(stitched, bg)
    if bbox:
        trim = min(max(bbox[2] + 32, min_width), width)
        stitched = stitched.crop((0, 0, trim, height))
    path = tempfile.mktemp(suffix=".png", prefix="comments_")
    stitched.save(path)
    output = await read_binary(path)
    os.remove(path)
    if low_quality:
        output = await png_to_jpg(output)
    return output, stitched.width


async def screenshot_comments(
    url: str,
    count: int = 10,
    force_dark: bool = True,
    low_quality: bool = False,
):
    """
    Take a long screenshot of the first `count` top-level comments of a
    post on one of COMMENT_SITES, as they appear on the page.
    Yields it in parts of about COMMENTS_PART_HEIGHT as they're captured;
    use with contextlib.aclosing so the browser is closed if not finished.
    """
    site = comment_site(url)
    if not site:
        raise CommentsUnavailable("Unsupported site")
    conf = COMMENT_SITES[site]
    # Placeholders shown while comments load have no text
    items = f"Array.from({conf['items']}).filter(e => e.innerText.trim())"
    expand = conf["expand"] or "el => {}"
    browser = None
    shots = []
    taken = 0
    # Parts keep at least the width of the ones before, so the text is
    # the same size in each when they're viewed one at a time
    part_width = 0
    try:
        browser = await _start_browser(force_dark)
        page = await browser.get(_comments_url(site, url))
        await page
        await asyncio.sleep(5)

        location = await page.evaluate("location.href")
        if any(m in location for m in LOGIN_WALL_MARKERS):
            raise CommentsUnavailable("Login required")
        if conf["open"]:
            await page.evaluate(conf["open"])
            await asyncio.sleep(3)

        # Comments load lazily: keep scrolling the newest one into view
        found = 0
        for _ in range(10 + count):
            found = await page.evaluate(f"""
                (() => {{
                    const items = {items};
                    if (items.length) items[items.length - 1].scrollIntoView({{block: 'center'}});
                    else window.scrollBy(0, window.innerHeight / 2);
                    return items.length;
                }})()
            """)
            if found >= count:
                break
            await asyncio.sleep(2)
        if not found:
            captcha = await page.evaluate(
                "!!document.querySelector(\"[id*='captcha' i], [class*='captcha' i]\")"
                "?.getClientRects().length"
            )
            if captcha:
                raise CommentsUnavailable("The site asked to solve a captcha")
            raise CommentsUnavailable("No comments found")
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)
        # Show the first comments once so lazily loaded icons/avatars load
        for i in range(min(found, count)):
            await page.evaluate(f"{items}[{i}]?.scrollIntoView({{block: 'center'}})")
            await asyncio.sleep(0.5)
        await asyncio.sleep(2)

        # Keep sticky headers/players from covering the comments. Visibility
        # is inherited, so leave alone the ones the comments sit inside.
        await page.evaluate(f"""
            (() => {{
                const first = {items}[0];
                document.querySelectorAll('*').forEach(el => {{
                    const pos = window.getComputedStyle(el).position;
                    if ((pos === 'fixed' || pos === 'sticky') && !el.contains(first))
                        el.style.visibility = 'hidden';
                }});
                window.__shotKeys = new Set();
            }})()
        """)

        # Take the comments one at a time, picking the first one not taken
        # yet: X unloads tweets scrolled past, so indexes don't stay valid
        misses = 0
        while taken < count and misses < 5:
            picked = await page.evaluate(f"""
                (() => {{
                    const items = {items};
                    const key = el => el.innerText.slice(0, 150);
                    const el = items.find(e => !window.__shotKeys.has(key(e)));
                    if (!el) {{
                        if (items.length) items[items.length - 1].scrollIntoView({{block: 'center'}});
                        return null;
                    }}
                    window.__shotKeys.add(key(el));
                    window.__shotEl = el;
                    el.scrollIntoView({{block: 'start'}});
                    ({expand})(el);
                    return true;
                }})()
            """)
            if not picked:
                misses += 1
                await asyncio.sleep(2)
                continue
            misses = 0
            # Let the expanded text and lazily loaded icons/avatars render
            await asyncio.sleep(1.5)
            # Page coordinates from the top of the comment to the top of the
            # next one, so the spacing between them is kept. If something
            # skipped (like an ad) sits in between, stop at the comment.
            rect = await page.evaluate(f"""
                (() => {{
                    const el = window.__shotEl;
                    if (!el || !el.isConnected) return null;
                    const items = {items};
                    const next = items[items.indexOf(el) + 1];
                    const r = el.getBoundingClientRect();
                    let bottom = r.bottom;
                    if (next) {{
                        const top = next.getBoundingClientRect().top;
                        if (top >= r.bottom && top - r.bottom < 48) bottom = top;
                    }}
                    return JSON.stringify({{
                        x: r.left + window.scrollX,
                        y: r.top + window.scrollY,
                        width: r.width,
                        height: bottom - r.top,
                    }});
                }})()
            """)
            if not rect:
                continue
            rect = json.loads(rect)
            if rect["width"] < 10 or rect["height"] < 10:
                continue
            shot = await _capture_region(
                page, rect["x"], rect["y"], rect["width"], rect["height"]
            )
            if _is_blank(shot):
                continue
            shots.append(shot)
            taken += 1
            if sum(s.height for s in shots) >= COMMENTS_PART_HEIGHT:
                image, part_width = await _stitch_comments(
                    shots, low_quality, part_width
                )
                yield image
                shots = []
        if shots:
            image, part_width = await _stitch_comments(shots, low_quality, part_width)
            yield image
    finally:
        if browser:
            await _stop_browser(browser)

    if not taken:
        raise CommentsUnavailable("Comments didn't render")


async def save_cookies_txt(browser, path=".cookies.txt"):
    result = await browser.cookies.get_all()

    with open(path, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in result:
            if c.domain is None or c.domain == "":
                domain = c.host  # CDP provides .host for host‑only cookies
                flag = "FALSE"
            else:
                domain = c.domain if c.domain.startswith(".") else f".{c.domain}"
                flag = "TRUE" if domain.startswith(".") else "FALSE"
            path_val = c.path if c.path.startswith("/") else "/"
            secure = "TRUE" if c.secure else "FALSE"
            if c.expires is None or c.expires <= 0:
                expires = 0
            else:
                expires = int(c.expires)

            f.write(f"{domain}\t{flag}\t{path_val}\t{secure}\t{expires}\t{
                    c.name}\t{
                    c.value}\n")


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

    parts = list(map(int, s.split(":")))

    # Seconds (last part) must be 0-59
    if parts[-1] < 0 or parts[-1] > 59:
        return False

    # Minutes (if present) must be 0-59
    if len(parts) >= 2 and (parts[-2] < 0 or parts[-2] > 59):
        return False

    # Hours (if present) must be >=0 (no upper limit)
    return not (len(parts) == 3 and parts[0] < 0)


async def read_binary(path: str):
    def stdlib_read(file):
        with open(file, "rb") as f:
            return f.read()

    return await sync_to_async(stdlib_read, path)


async def write_binary(path: str, bytes_: bytes):
    def stdlib_write(file, bytes_):
        with open(file, "wb") as f:
            f.write(bytes_)

    return await sync_to_async(stdlib_write, path, bytes_)


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
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        path,
    )
    if rc != 0:
        raise RuntimeError(f"ffprobe failed on {path}")
    return json.loads(stdout)


async def get_fps(video_path: str) -> Fraction:
    stdout, stderr, rc = await _run(
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    )

    if rc != 0:
        raise RuntimeError(stderr.decode().strip())

    return Fraction(stdout.decode().strip())


async def get_mediainfo(video_path: str, full=False, html=False) -> str:
    args = ["mediainfo"]
    if full:
        args.append("--Full")
    if html:
        args.append("--Output=HTML")
    stdout, stderr, rc = await _run(
        *args,
        video_path,
    )

    if rc != 0:
        raise RuntimeError(stderr.decode().strip())

    return stdout.decode().strip()


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
        if bitrate_kbps > 8500:
            issues.append(
                f"video bitrate={bitrate_kbps} kbps (exceeds 4,500 kbps WhatsApp limit)"
            )

        if codec not in ("h264", "hevc"):
            issues.append(f"codec={codec} (WhatsApp expects H.264 or HEVC)")

    audio = _get_audio_stream(info)
    if audio:
        sample_rate = int(audio.get("sample_rate", 0))
        if sample_rate not in (44100, 48000):
            issues.append(f"audio sample rate={sample_rate} Hz (use 44100 or 48000)")

    return issues


async def normalize_for_whatsapp(
    input_path: str, output_path: str, transcode: bool = False
):
    video = _get_video_stream(await probe_video(input_path))
    codec = video.get("codec_name", "h264") if video else "h264"

    if not transcode:
        # Remux only
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            "-map_metadata",
            "-1",
            output_path,
        ]
    elif codec == "hevc":
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-c:v",
            "libx265",
            "-preset",
            "fast",
            "-crf",
            "28",
            "-maxrate",
            "8000k",
            "-bufsize",
            "16000k",
            "-tag:v",
            "hvc1",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            "-map_metadata",
            "-1",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg",
            "-err_detect",
            "ignore_err",
            "-y",
            "-i",
            input_path,
            "-c:v",
            "libx264",
            "-crf",
            "23",
            "-maxrate",
            "8000k",
            "-bufsize",
            "16000k",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            "-map_metadata",
            "-1",
            output_path,
        ]

    _, stderr, rc = await _run(*cmd)
    if rc != 0:
        raise NormalizeVidError(f"ffmpeg failed: {stderr.decode()}")


class LimitedDict(OrderedDict):
    def __init__(self, maxsize=128, *args, **kwds):
        self.maxsize = maxsize
        super().__init__(*args, **kwds)

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.maxsize:
            oldest = next(iter(self))
            del self[oldest]
