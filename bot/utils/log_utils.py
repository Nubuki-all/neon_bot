import traceback

from bot import LOGS, bot, conf, jid


async def group_logger(
    Exception: Exception, e: str, error: bool, critical: bool, warning: bool
):
    if not conf.LOG_GROUP:
        return
    try:
        trace = e or traceback.format_exc()
        gc = conf.LOG_GROUP.split(":")
        chat, server = map(str, gc) if len(gc) > 1 else (str(gc[0]), "g.us")
        if critical:
            pre = "CRITICAL ERROR"
        elif warning:
            pre = "WARNING"
        elif error or not e:
            pre = "ERROR"
        else:
            pre = "INFO"
        msg = await bot.client.send_message(
            jid.build_jid(chat, server),
            f"*#{pre}*\n\n*Summary of what happened:*\n> {trace}\n\n*To restict error messages to logs unset the* `conf.LOG_GROUP` *env var*.",
        )
        return msg
    except Exception:
        LOGS.error(traceback.format_exc())


def log(
    Exception: Exception = None,
    e: str = None,
    critical=False,
    error=False,
    warning=False,
):
    trace = e or traceback.format_exc()
    if critical:
        _log = LOGS.critical
    elif warning:
        _log = LOGS.warning
    elif error or not e:
        _log = LOGS.error
    else:
        _log = LOGS.info
    _log(trace)


async def logger(
    Exception: Exception = None,
    e: str = None,
    critical=False,
    error=False,
    warning=False,
):
    log(Exception, e, error, critical, warning)
    await group_logger(Exception, e, error, critical, warning)
