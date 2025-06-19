import signal

import aiohttp

from bot import Message, asyncio, bot, conf, jid, sys, version_file
from bot.fun.emojis import enmoji, enmoji2
from bot.fun.quips import enquip, enquip2
from bot.utils.bot_utils import shutdown_services
from bot.utils.db_utils import backup_wa_db
from bot.utils.log_utils import logger
from bot.utils.msg_rank import scheduler2
from bot.utils.msg_store import Base as sql_base
from bot.utils.msg_store import auto_save_msg, engine
from bot.utils.msg_utils import send_presence
from bot.utils.rss_utils import scheduler


async def onrestart():
    try:
        if sys.argv[1] == "restart":
            msg = "*Restarted!*"
        elif sys.argv[1].startswith("update"):
            s = sys.argv[1].split()[1]
            if s == "True":
                with open(version_file, "r") as file:
                    v = file.read()
                msg = f"*Updated to >>>* {v}"
            else:
                msg = "*No major update found!*\n" f"Bot restarted! {enmoji()}"
        else:
            return
        chat_id, msg_id, server = map(str, sys.argv[2].split(":"))
        await bot.client.edit_message(
            jid.build_jid(chat_id, server), msg_id, Message(conversation=msg)
        )
    except Exception:
        await logger(Exception)


async def onstart(text="*Please restart me.*"):
    i = conf.OWNER.split()[0]
    await bot.client.send_message(
        jid.build_jid(i),
        text,
    )


async def on_termination():
    try:
        dead_msg = f"*I'm* {enquip2()} {enmoji2()}"
        i = conf.OWNER.split()[0]
        await bot.client.send_message(
            jid.build_jid(i),
            dead_msg,
        )
    except Exception:
        pass
    # More cleanup code?
    await shutdown_services()
    await bot.client.stop()


async def update_presence():
    while True:
        try:
            await send_presence()
            await asyncio.sleep(5)
            await send_presence(False)
        except Exception:
            pass
        await asyncio.sleep(600)


async def backup_database():
    if not conf.BACKUP_WA_DB and conf.WA_DB:
        return
    prevent_spam = True
    while True:
        if bot.stop_back_up:
            return
        try:
            if not prevent_spam:
                await backup_wa_db()
                await logger(e="Backed up database!")
            else:
                prevent_spam = False
        except Exception:
            await logger(Exception)
        await asyncio.sleep(conf.WA_DB_BACKUP_INTERVAL)


async def on_startup():
    try:
        loop = asyncio.get_running_loop()
        bot.requests = aiohttp.ClientSession(loop=loop)
        for signame in {"SIGINT", "SIGTERM", "SIGABRT"}:
            loop.add_signal_handler(
                getattr(signal, signame),
                lambda: asyncio.create_task(on_termination()),
            )
        async with engine.begin() as conn:
            await conn.run_sync(sql_base.metadata.create_all)
        while not bot.is_connected:
            await asyncio.sleep(1)
        scheduler.start()
        scheduler2.start()
        if len(sys.argv) == 3:
            await onrestart()
        else:
            await onstart(f"*I'm {enquip()} {enmoji()}*")
        asyncio.create_task(update_presence())
        asyncio.create_task(backup_database())
        asyncio.create_task(auto_save_msg())
        await logger(e="Bot has started.")
    except Exception:
        await logger(Exception)
