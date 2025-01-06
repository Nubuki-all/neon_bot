import logging
import signal
import traceback
from decouple import config
from neonize.aioze.client import NewAClient
from neonize.events import event
from neonize.utils import log


async def gen():

    def interrupted(*_):
        event.set()

    signal.signal(signal.SIGINT, interrupted)

    log.setLevel(logging.DEBUG)

    PH_NUMBER = config("PH_NUMBER")

    client = NewAClient(wa_db)
    await client.PairPhone(
        PH_NUMBER,
        show_push_notification=True,
    )


try:
    if __name__ == "__main__":
        asyncio.run(gen())
except Exception:
    traceback.print_exc()
