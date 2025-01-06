import traceback

from bot import LOGS


def log(Exception: Exception = None, e: str = None, critical=False):
    trace = e or traceback.format_exc()
    LOGS.info(trace) if not critical else LOGS.critical(trace)


async def logger(Exception: Exception = None, e: str = None, critical=False):
    log(Exception, e, critical)
