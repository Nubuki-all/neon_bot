import asyncio

from bs4 import BeautifulSoup
from feedparser import parse as feedparse

from bot import rss_dict_lock
from bot.config import bot, conf
from bot.workers.auto.schedule import addjob, scheduler

from .db_utils import save2db2
from .log_utils import log
from .msg_utils import parse_and_send_rss


async def rss_monitor():
    """
    An asynchronous function to get rss links
    """
    if not conf.RSS_CHAT:
        log(e="RSS_CHAT not set! Shutting down rss scheduler...")
        scheduler.shutdown(wait=False)
        return
    if len(bot.rss_dict) == 0:
        scheduler.pause()
        return
    all_paused = True
    for title, data in list(bot.rss_dict.items()):
        try:
            if data["paused"]:
                continue
            rss_d = feedparse(data["link"])
            try:
                last_link = rss_d.entries[0]["links"][1]["href"]
            except IndexError:
                last_link = rss_d.entries[0]["link"]
            finally:
                all_paused = False
            last_title = rss_d.entries[0]["title"]
            if data["last_feed"] == last_link or data["last_title"] == last_title:
                continue
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
                }
                feed_list.append(feed_)
                feed_count += 1
            for feed_ in reversed(feed_list):
                await parse_and_send_rss(feed_, data["chat"])
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
            log(e=f"{e} - Feed Name: {title} - Feed Link: {data['link']}")
            continue
    if all_paused:
        scheduler.pause()
        log(e="No active rss feed\nRss Monitor has been paused!")
    elif not bot.rss_ran_once:
        bot.rss_ran_once = True


def get_pic_url(feed: dict) -> list | None:
    if feed.get("content"):
        content = feed["content"][0]["value"]
    else:
        return
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


def schedule_gift_monitor():
    addjob(conf.RSS_DELAY, gift_code_monitor, "1", "gift_monitor")


schedule_rss()
# scheduler.start()
