import asyncio
import datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from dateutil import parser as dateutil_parser
from neonize.utils.jid import build_jid

from bot.config import bot
from bot.utils.db_utils import save2db2
from bot.utils.log_utils import log

scheduler = AsyncIOScheduler(timezone=pytz.UTC)


async def send_reminder_async(
    chat_id: str, user_id: str, store: dict, from_scheduler: bool = False
):
    if from_scheduler:
        log(e=f"Reminder #{store["id"]} is due")
    else:
        log(e=f"Reminder #{store["id"]} was missed due to downtime")
    chat_jid = build_jid(chat_id.split("@")[0], chat_id.split("@")[1])
    await bot.client.reply_message(
        "@" + user_id + ": *Reminder*",
        store["message"],
        chat_jid,
        # mentions_are_lids=store["lid_address"],
    )
    bot.remind_dict.setdefault(chat_id, {}).setdefault(user_id, {}).pop(store["id"])
    await save2db2(bot.remind_dict, "reminders")


def parse_iso_to_utc(iso_str: str, assume_tz: str = "Africa/Lagos"):
    dt = dateutil_parser.isoparse(iso_str)
    if dt.tzinfo is None:
        dt = pytz.timezone(assume_tz).localize(dt)
    return dt.astimezone(pytz.UTC)


async def schedule_reminder_async(
    reminder_uuid: str,
    store: dict,
    chat_id: str,
    user_id: str,
    assume_tz: str = "Africa/Lagos",
):
    iso = store.get("time")
    if not iso:
        return
    run_dt_utc = parse_iso_to_utc(iso, assume_tz)
    now_utc = datetime.datetime.now(pytz.UTC)
    if run_dt_utc <= now_utc:
        asyncio.create_task(send_reminder_async(chat_id, user_id, store))
        return

    trigger = DateTrigger(run_date=run_dt_utc, timezone=pytz.UTC)
    # schedule a small wrapper which will create the coroutine task at run-time
    scheduler.add_job(
        func=send_reminder_async,
        trigger=trigger,
        args=(chat_id, user_id, store, True),
        id=reminder_uuid,
        name="Reminders",
        replace_existing=True,
        misfire_grace_time=60,
    )


def cancel_reminder(reminder_uuid: str):
    try:
        scheduler.remove_job(reminder_uuid)
    except Exception:
        pass


async def reschedule_all(assume_tz: str = "Africa/Lagos"):
    for chat_id, users in list(bot.remind_dict.items()):
        for user_id, reminders in list(users.items()):
            for rid, store in list(reminders.items()):
                await schedule_reminder_async(rid, store, chat_id, user_id, assume_tz)
