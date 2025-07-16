import inspect
import logging
import traceback

from bot import bot, conf, jid


def get_logger_from_caller():
    # Get the frame of the caller
    frame = inspect.stack()[2].frame
    module = inspect.getmodule(frame)
    name = module.__name__ if module else "__main__"
    return logging.getLogger(name)


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
        logger = get_logger_from_caller()
        logger.error(traceback.format_exc())


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
    log(Exception, e, error, critical, warning)
    await group_logger(Exception, e, error, critical, warning)
