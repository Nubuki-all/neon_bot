import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from random import uniform

import httpx
from bs4 import BeautifulSoup
from feedparser import parse as feedparse

from bot import rss_dict_lock
from bot.config import bot, conf
from bot.workers.auto.schedule import addjob, scheduler

from .db_utils import save2db2
from .log_utils import log
from .msg_utils import parse_and_send_rss

# How many feeds to fetch/send concurrently.
_CONCURRENCY = getattr(conf, "RSS_CONCURRENCY", 5)
_semaphore = asyncio.Semaphore(_CONCURRENCY)

# Reused across requests so we get connection pooling/keep-alive instead of
# a fresh TCP+TLS handshake per feed per cycle.
_http_client = httpx.AsyncClient(
    headers={
        "User-Agent": getattr(
            conf,
            "RSS_USER_AGENT",
            "Mozilla/5.0 (compatible; RSSBot/1.0; +https://example.com)",
        ),
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    },
    timeout=httpx.Timeout(connect=10, read=20, write=10, pool=10),
    follow_redirects=True,
)

# Tracks consecutive transient failures per feed so we can back off instead
# of hammering a feed that's erroring. Deliberately in-memory only (not
# persisted) - it resets on restart, which is fine since it's just a
# rate-limiting aid, not real state.
_error_state: dict[str, dict] = {}

BASE_BACKOFF = 5
MAX_BACKOFF = 300


def _is_transient_error(exc: Exception | None) -> bool:
    """
    True for errors that mean "something is temporarily wrong, slow down",
    as opposed to expected control-flow errors (e.g. IndexError from
    walking past the last feed entry, which is normal and needs no backoff).
    Used on the *send* path (WhatsApp via neonize), separate from the
    httpx fetch path below which has its own, more specific handling.
    """
    if exc is None:
        return False
    return isinstance(
        exc, (OSError, TimeoutError, ConnectionError, asyncio.TimeoutError)
    )


async def _backoff_sleep(title: str, delay: float | None = None):
    """
    Sleep before this feed is touched again. If `delay` isn't given,
    computes an exponential backoff (with jitter) from this feed's
    consecutive-failure count.
    """
    state = _error_state.setdefault(title, {"count": 0})
    state["count"] += 1
    if delay is None:
        delay = min(BASE_BACKOFF * (2 ** (state["count"] - 1)), MAX_BACKOFF)
        # jitter so feeds don't all retry in lockstep
        delay += uniform(0, delay * 0.1)
    log(e=f"Feed '{title}' backing off {
            delay:.1f}s (attempt {
            state['count']})")
    await asyncio.sleep(delay)


def _reset_backoff(title: str):
    _error_state.pop(title, None)


def _parse_retry_after(value: str) -> float | None:
    """Retry-After can be either an integer number of seconds or an HTTP date."""
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max((dt - datetime.now(timezone.utc)).total_seconds(), 0)
    except (TypeError, ValueError):
        return None


async def _fetch_feed(title: str, link: str):
    """
    Fetch a feed over HTTP with httpx (so we get real status codes and
    timeout types) and hand the bytes to feedparser to parse. Returns a
    parsed feedparser dict, or None if the fetch failed / was rate
    limited / should be skipped this cycle.
    """
    try:
        resp = await _http_client.get(link)
    except httpx.TimeoutException as e:
        log(e=f"Timeout fetching feed '{title}': {e}")
        await _backoff_sleep(title)
        return None
    except httpx.HTTPError as e:
        log(e=f"Error fetching feed '{title}': {e}")
        await _backoff_sleep(title)
        return None

    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After")
        wait = _parse_retry_after(retry_after) if retry_after else None
        log(e=f"Feed '{title}' rate limited (429)")
        await _backoff_sleep(title, delay=wait)
        return None

    if resp.status_code >= 500:
        log(e=f"Feed '{title}' returned {resp.status_code}")
        await _backoff_sleep(title)
        return None

    if resp.status_code >= 400:
        log(e=f"Feed '{title}' returned {resp.status_code} - {link}")
        return None

    _reset_backoff(title)
    rss_d = await asyncio.to_thread(feedparse, resp.content)
    if getattr(rss_d, "bozo", 0):
        # This is a parse warning (malformed XML etc.), not a network
        # issue - httpx already got us a 200, so no backoff, just a note.
        log(e=f"Feed '{title}' parsed with warnings: {rss_d.get('bozo_exception')}")
    return rss_d


async def rss_monitor():
    """
    An asynchronous function to get rss links.
    Each feed runs as its own task so a slow or erroring feed can't block
    the others.
    """
    if not conf.RSS_CHAT:
        log(e="RSS_CHAT not set! Shutting down rss scheduler...")
        scheduler.shutdown(wait=False)
        return
    if len(bot.rss_dict) == 0:
        scheduler.pause()
        return

    items = list(bot.rss_dict.items())
    active_items = [(title, data) for title, data in items if not data["paused"]]

    if not active_items:
        scheduler.pause()
        log(e="No active rss feed\nRss Monitor has been paused!")
        return

    results = await asyncio.gather(
        *(process_feed(title, data) for title, data in active_items),
        return_exceptions=True,
    )

    for (title, data), result in zip(active_items, results):
        if isinstance(result, Exception):
            # Safety net - process_feed handles its own errors internally,
            # so anything landing here is unexpected and worth logging loudly.
            log(e=f"{result} - Feed Name: {title} - Feed Link: {data['link']}")

    if not bot.rss_ran_once:
        bot.rss_ran_once = True


async def process_feed(title: str, data: dict):
    """
    Fetch and process a single RSS feed. Runs as its own task (bounded by
    a semaphore) so it can be slow or back off without holding up any
    other feed.
    """
    async with _semaphore:
        rss_d = await _fetch_feed(title, data["link"])
        if rss_d is None:
            return

        if not rss_d.entries:
            log(e=f"No entries returned for feed: {title}")
            return

        _reset_backoff(title)

        try:
            try:
                last_link = rss_d.entries[0]["links"][1]["href"]
            except IndexError:
                last_link = rss_d.entries[0]["link"]
            last_title = rss_d.entries[0]["title"]
            if data["last_feed"] == last_link or data["last_title"] == last_title:
                return

            if not bot.rss_ran_once:
                data["allow_rss_spam"] = True

            feed_count = 0
            feed_list = []
            while True:
                try:
                    author = rss_d.entries[feed_count].get("author")
                    item_title = rss_d.entries[feed_count]["title"]
                    pic = get_pic_url(rss_d.entries[feed_count])
                    if content := rss_d.entries[feed_count].get("content"):
                        content = content[0]["value"]
                    summary = rss_d.entries[feed_count]["summary"]
                    try:
                        url = rss_d.entries[feed_count]["links"][1]["href"]
                    except IndexError:
                        url = rss_d.entries[feed_count]["link"]
                    if data["last_feed"] == url or data["last_title"] == item_title:
                        break
                except IndexError:
                    log(
                        e=f"Reached Max index no. {feed_count} for this feed: {title}. Maybe you need to use less RSS_DELAY to not miss some torrents"
                    )
                    if not data.get("allow_rss_spam"):
                        log(e="Due to spam prevention, RSS feed has been reset.")
                        feed_list = []
                    break

                parse = True
                for flist in data["inf"]:
                    if all(x not in item_title.lower() for x in flist):
                        parse = False
                        feed_count += 1
                        break
                for flist in data["exf"]:
                    if any(x in item_title.lower() for x in flist):
                        parse = False
                        feed_count += 1
                        break
                if not parse:
                    continue

                feed_ = {
                    "author": author,
                    "link": url,
                    "pic": pic,
                    "content": content,
                    "summary": summary,
                    "title": item_title,
                    "pin": data.get("pin_messages", False),
                }
                feed_list.append(feed_)
                feed_count += 1

            for feed_ in reversed(feed_list):
                await _send_with_retry(feed_, data, title)
                await asyncio.sleep(1)

            async with rss_dict_lock:
                bot.rss_dict[title].update(
                    {
                        "allow_rss_spam": False,
                        "last_feed": last_link,
                        "last_title": last_title,
                    }
                )
            await save2db2(bot.rss_dict, "rss")
            log(e=f"Feed Name: {title}")
            log(e=f"Last item: {last_link}")

        except Exception as e:
            if _is_transient_error(e):
                await _backoff_sleep(title)
            else:
                log(e=f"{e} - Feed Name: {title} - Feed Link: {data['link']}")


async def _send_with_retry(feed_: dict, data: dict, title: str):
    """
    Send a single feed item, sleeping and retrying on errors that look
    transient (network hiccups, connection drops).
    Todo: actually retry on errors
    """
    while True:
        try:
            await parse_and_send_rss(feed_, data["chat"])
            return
        except Exception as e:
            # if _is_transient_error(e):
            #     await _backoff_sleep(title)
            #     continue
            log(
                e=f"{e} - Feed Name: {title} - failed sending item: {feed_.get('title')}"
            )
            return


def get_pic_url(feed: dict) -> list | None:
    if feed.get("content"):
        content = feed["content"][0]["value"]
    else:
        return []
    pics = []
    soups = BeautifulSoup(content, "html.parser")
    for soup in soups.find_all("img"):
        pic = soup["src"]
        if pic:
            pic = pic.split("?x-oss")[0]
            pics.append(pic)
    return pics


def schedule_rss():
    addjob(conf.RSS_DELAY, rss_monitor)


schedule_rss()
# scheduler.start()
