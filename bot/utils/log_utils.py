import inspect
import logging
import traceback

from bot import bot, conf, jid

from .bot_utils import sync_to_async

_log_ = logging.getLogger(__name__)


def get_logger_from_caller():
    """
    Walk up the call stack until you find a frame whose module name
    isn’t this one, and return a Logger for that module.
    """
    blacklist = [
        __name__,
        "concurrent.futures.thread",
        "bot.utils.bot_utils",
    ]
    frame = inspect.currentframe()
    # skip our own get_logger_from_caller frame
    frame = frame.f_back
    max_look_backs = 4

    while frame and max_look_backs:
        module = inspect.getmodule(frame)
        name = module.__name__ if module else None
        # first frame not in this module → the caller
        if name and name not in blacklist:
            return logging.getLogger(name)
        frame = frame.f_back
        max_look_backs -= 1

    # fallback if all else fails
    return logging.getLogger(current_module)


async def group_logger(
    Exception: Exception = None,
    e: str = None,
    error: bool = False,
    critical: bool = False,
    warning: bool = False,
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
            f"*#{pre}*\n\n*Summary of what happened:*\n> {trace}\n\n*To restrict error messages to logs unset the* `conf.LOG_GROUP` *env var*.",
        )
        return msg
    except Exception:
        _log_.error(traceback.format_exc())


def log(
    Exception: Exception = None,
    e: str = None,
    critical: bool = False,
    error: bool = False,
    warning: bool = False,
):
    trace = e or traceback.format_exc()
    logger = get_logger_from_caller()

    if critical:
        logger.critical(trace)
    elif warning:
        logger.warning(trace)
    elif error or not e:
        logger.error(trace)
    else:
        logger.info(trace)


async def logger(
    Exception: Exception = None,
    e: str = None,
    critical: bool = False,
    error: bool = False,
    warning: bool = False,
):
    await sync_to_async(log, Exception, e, error, critical, warning)
    await group_logger(Exception, e, error, critical, warning)
