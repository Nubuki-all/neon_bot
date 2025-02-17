import traceback

from bot import LOGS, bot, conf, jid


async def group_logger(Exception: Exception, e: str):
    if not conf.LOG_GROUP:
        return
    try:
        error = e or traceback.format_exc()
        gc = conf.LOG_GROUP.split(":")
        chat, server = map(str, gc) if len(gc) > 1 else (str(gc[0]), "g.us")
        msg = await bot.client.send_message(
            jid.build_jid(chat, server),
            f"*#ERROR*\n\n*Summary of what happened:*\n> {error}\n\n*To restict error messages to logs unset the* `conf.LOG_GROUP` *env var*.",
        )
        return msg
    except Exception:
        LOGS.info(traceback.format_exc())


def log(Exception: Exception = None, e: str = None, critical=False):
    trace = e or traceback.format_exc() or "Logger wasn't configured properly!"
    LOGS.info(trace) if not critical else LOGS.critical(trace)


async def logger(Exception: Exception = None, e: str = None, critical=False):
    log(Exception, e, critical)
    await group_logger(Exception, e)
