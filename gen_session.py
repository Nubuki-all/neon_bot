import asyncio
import logging
import signal
import sys
import traceback
from decouple import config
from neonize.aioze.client import NewAClient
from neonize.events import ConnectedEv
from neonize.utils import log

client = NewAClient(config("WA_DB"))
log.setLevel(logging.DEBUG)
pn = config("PH_NUMBER")

qr = False
if len(sys.argv) > 1:
    qr = True


@client.event(ConnectedEv)
async def on_connected(client: NewAClient, __: ConnectedEv):
    await client.stop()


async def on_exit():
    await client.stop()


async def gen():
    for signame in {"SIGINT", "SIGTERM", "SIGABRT"}:
        client.loop.add_signal_handler(
            getattr(signal, signame),
            lambda: asyncio.create_task(on_exit()),
        )
    await client.PairPhone(
        pn,
        show_push_notification=True,
    ) if not qr and pn else await client.connect()


try:
    if __name__ == "__main__":
        client.loop.run_until_complete(gen())
except Exception:
    traceback.print_exc()
