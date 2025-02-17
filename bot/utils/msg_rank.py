import asyncio
import datetime

from bot import jid
from bot.config import bot
from bot.workers.auto.schedule import scheduler2
from bot.workers.handlers.wa import get_ranking_msg

from .bot_utils import same_week
from .db_utils import save2db2
from .log_utils import logger


async def auto_rank():
    """
    Sends the msg ranks of each chat daily
    """
    try:
        groups = bot.group_dict
        write = False
        for group in list(groups):
            if group in ("last_rank_clear"):
                continue
            group_info = groups[group]
            if not group_info.get("msg_chat"):
                continue
            msg = await get_ranking_msg(group, tag=True)
            if not msg:
                continue
            await bot.client.send_message(jid.build_jid(group, "g.us"), msg)
            await asyncio.sleep(3)
            if not (last_clear := groups.get("last_rank_clear")):
                groups["last_rank_clear"] = datetime.datetime.today()
            elif same_week(last_clear, 1):
                continue
            write = True
            update_users_rank(group)
            group_info.setdefault("msg_ranking", {}).clear()
            await bot.client.send_message(
                jid.build_jid(group, "g.us"), "*Message ranking has been reset.*"
            )
            await asyncio.sleep(3)
        if write:
            groups.update(
                last_rank_clear=(datetime.datetime.today() + datetime.timedelta(days=2))
            )
            await save2db2(bot.group_dict, "groups")
    except Exception:
        await logger(Exception)


def update_users_rank(chat_id):
    group = bot.group_dict.setdefault(chat_id, {})
    msg_rank_dict = group.setdefault("msg_ranking")
    sorted_ms_rank_dict = dict(
        sorted(msg_rank_dict.items(), key=lambda item: item[1], reverse=True),
    )
    sorted_ms_rank_dict.pop("total")
    t_three = [1, 2, 3]
    for i, user in zip(t_three, list(sorted_ms_rank_dict.keys())):
        user_rank = group.setdefault("msg_stats", {}).setdefault(user, {})
        user_rank[i] = user_rank.setdefault(i, 0) + 1


scheduler2.add_job(id="msg_ranking", func=auto_rank, trigger="cron", hour=20)
