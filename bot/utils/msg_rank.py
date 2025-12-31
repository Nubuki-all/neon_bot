import asyncio
import datetime

from bot import jid
from bot.config import bot
from bot.workers.auto.schedule import scheduler2
from bot.workers.handlers.wa import get_ranking_msg

from .bot_utils import same_month, same_week
from .db_utils import save2db2
from .log_utils import logger


async def auto_rank():
    groups = bot.group_dict
    write_week = False
    write_month = False

    # Weekly window (evaluate once)
    weekly_clear = groups.get("last_rank_clear")
    weekly_window = not weekly_clear or not same_week(weekly_clear, 1)

    for group in list(groups):
        try:
            if group in ("last_rank_clear", "last_monthly_rank_clear"):
                continue

            group_info = groups[group]

            if not group_info.get("msg_chat"):
                continue
            if group_info.get("left"):
                continue

            ranking = group_info.setdefault("msg_ranking", {})
            period = ranking.get("period", "weekly")

            # Monthly groups only send during weekly window
            if period == "monthly" and not weekly_window:
                continue

            msg = await get_ranking_msg(group, tag=True)
            if not msg:
                continue

            server = ranking.get("server")

            await bot.client.send_message(
                jid.build_jid(group, "g.us"),
                msg,
                mentions_are_lids=(server == 0),
            )

            await asyncio.sleep(3)

            # ---------- RESET LOGIC ----------
            if period == "weekly":
                if not (last_clear := groups.get("last_rank_clear")):
                    groups["last_rank_clear"] = datetime.datetime.today()
                elif not weekly_window:
                    continue

                write_week = True

            else:  # monthly
                if not (last_clear := groups.get("last_monthly_rank_clear")):
                    groups["last_monthly_rank_clear"] = datetime.datetime.today()
                elif same_month(last_clear, 1):
                    continue

                write_month = True
            saved_config = {
                "period": ranking.get("period", "weekly"),
                "server": ranking.get("server"),
            }
            update_users_rank(group)
            ranking.clear()
            ranking.update(saved_config)

            await bot.client.send_message(
                jid.build_jid(group, "g.us"),
                f"*{period.capitalize()} message ranking has been reset.*",
            )

            await asyncio.sleep(3)

        except Exception:
            await logger(
                e=f"Error occurred while handling message ranking for group with id: {group}",
                error=True,
            )
            await logger(Exception)

    try:
        if write_week:
            groups["last_rank_clear"] = datetime.datetime.today() + datetime.timedelta(
                days=2
            )
        if write_month:
            groups["last_monthly_rank_clear"] = datetime.datetime.today() + datetime.timedelta(
                days=2
            )

        if write_week or write_month:
            await save2db2(bot.group_dict, "groups")

    except Exception:
        await logger(Exception)


def update_users_rank(chat_id):
    group = bot.group_dict.setdefault(chat_id, {})
    msg_rank_dict = group.setdefault("msg_ranking", {})

    sorted_ms_rank_dict = dict(
        sorted(
            ((k, v) for k, v in msg_rank_dict.items() if isinstance(v, int)),
            key=lambda item: item[1],
            reverse=True,
        )
    )

    sorted_ms_rank_dict.pop("total", None)
    sorted_ms_rank_dict.pop("server", None)
    sorted_ms_rank_dict.pop("period", None)

    t_three = [1, 2, 3]
    for i, user in zip(t_three, list(sorted_ms_rank_dict.keys())):
        user_rank = group.setdefault("msg_stats", {}).setdefault(user, {})
        user_rank[i] = user_rank.setdefault(i, 0) + 1


scheduler2.add_job(
    id="msg_ranking",
    func=auto_rank,
    trigger="cron",
    hour=20,
    misfire_grace_time=None,
    max_instances=1,
)
