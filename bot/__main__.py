from bot.utils.os_utils import re_x

from . import asyncio  # noqa  # pylint: disable=unused-import
from . import (
    LOGS,
    ConnectedEv,
    DisconnectedEv,
    GroupInfoEv,
    JoinedGroupEv,
    LoggedOutEv,
    MessageEv,
    NewAClient,
    PairStatusEv,
    bot,
    conf,
    sys,
    time,
    traceback,
)
from .startup.after import on_startup
from .utils.db_utils import restore_wa_db
from .utils.events import POLL, Event, event_handler, on_message
from .utils.os_utils import re_x
from .utils.sudo_button_utils import poll_as_button_handler
from .workers.handlers.afk import activate_afk, afk_helper
from .workers.handlers.ani import airing, anime
from .workers.handlers.dev import bash, eval_message, get_logs
from .workers.handlers.fun import getmeme
from .workers.handlers.manage import (
    ban,
    delete,
    disable,
    disable_amr,
    enable,
    enable_amr,
    grt_toggle,
    pause_handler,
    restart_handler,
    rss_handler,
    sudoers,
    unban,
    update_handler,
    ytdl_disable,
    ytdl_enable,
)
from .workers.handlers.role import roles
from .workers.handlers.stuff import gc_info, getcmds, hello, up
from .workers.handlers.wa import gc_handler, sticker_reply
from .workers.handlers.yt import youtube_reply


@bot.client.event(ConnectedEv)
async def on_connected(_: NewAClient, __: ConnectedEv):
    bot.is_connected = True


@bot.client.event(PairStatusEv)
async def on_paired(_: NewAClient, message: PairStatusEv):
    LOGS.info(message)


@bot.client.event(LoggedOutEv)
async def on_logout(_: NewAClient, __: LoggedOutEv):
    LOGS.info("Bot has been logged out.")
    LOGS.info("Restarting…")
    time.sleep(10)
    re_x()


@bot.client.event(DisconnectedEv)
async def _(_: NewAClient, __: DisconnectedEv):
    if not bot.is_connected:
        LOGS.info("Restarting…")
        time.sleep(1)
        re_x()


@bot.register("start")
async def _(client: NewAClient, message: Event):
    await event_handler(message, hello)


@bot.register("pause")
async def _(client: NewAClient, message: Event):
    await event_handler(message, pause_handler)


@bot.register("logs")
async def _(client: NewAClient, message: Event):
    await event_handler(message, get_logs)


@bot.register("ping")
async def _(client: NewAClient, message: Event):
    await event_handler(message, up)


@bot.register("eval")
async def _(client: NewAClient, message: Event):
    await event_handler(message, eval_message, bot.client, require_args=True)


@bot.register("bash")
async def _(client: NewAClient, message: Event):
    await event_handler(message, bash, require_args=True)


@bot.register("meme")
async def _(client: NewAClient, message: Event):
    await event_handler(message, getmeme)


@bot.register("roles")
async def _(client: NewAClient, message: Event):
    await event_handler(message, roles, client)


@bot.register("cmds")
async def _(client: NewAClient, message: Event):
    await event_handler(message, getcmds)


@bot.register("afk")
async def _(client: NewAClient, message: Event):
    await event_handler(message, activate_afk)


@bot.register("rss")
async def _(client: NewAClient, message: Event):
    await event_handler(message, rss_handler, require_args=True)


@bot.register("anime")
async def _(client: NewAClient, message: Event):
    await event_handler(message, anime, require_args=True)


@bot.register("airing")
async def _(client: NewAClient, message: Event):
    await event_handler(message, airing, require_args=True)


@bot.register("ban")
async def _(client: NewAClient, message: Event):
    await event_handler(message, ban)


@bot.register("unban")
async def _(client: NewAClient, message: Event):
    await event_handler(message, unban)


@bot.register("gc_info")
async def _(client: NewAClient, message: Event):
    await event_handler(message, gc_info, bot.client)


@bot.register("greetings")
async def _(client: NewAClient, message: Event):
    await event_handler(message, grt_toggle, bot.client, require_args=True)


@bot.register("sudo")
async def _(client: NewAClient, message: Event):
    await event_handler(message, sudoers, bot.client)


@bot.register("disable")
async def _(client: NewAClient, message: Event):
    await event_handler(message, disable, bot.client)


@bot.register("enable")
async def _(client: NewAClient, message: Event):
    await event_handler(message, enable, bot.client)


@bot.register("amr_enable")
async def _(client: NewAClient, message: Event):
    await event_handler(message, enable_amr, bot.client)


@bot.register("amr_disable")
async def _(client: NewAClient, message: Event):
    await event_handler(message, disable_amr, bot.client)


@bot.register("ytdl_disable")
async def _(client: NewAClient, message: Event):
    await event_handler(message, ytdl_disable, bot.client)


@bot.register("ytdl_enable")
async def _(client: NewAClient, message: Event):
    await event_handler(message, ytdl_enable, bot.client)


@bot.register("del")
async def _(client: NewAClient, message: Event):
    await event_handler(message, delete, bot.client)


@bot.register("update")
async def _(client: NewAClient, message: Event):
    await event_handler(message, update_handler)


@bot.register("restart")
async def _(client: NewAClient, message: Event):
    await event_handler(message, restart_handler)


## AUTO ##


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await sticker_reply(message, None, client)


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await youtube_reply(message, None, client)


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await afk_helper(message, None, client)


@bot.register(POLL)
async def _(client: NewAClient, message: Event):
    await poll_as_button_handler(message)


@bot.client.event(MessageEv)
async def _(client: NewAClient, message: MessageEv):
    await on_message(client, message)


@bot.client.event(GroupInfoEv)
async def _(client: NewAClient, message: GroupInfoEv):
    await gc_handler(message)


@bot.client.event(JoinedGroupEv)
async def _(client: NewAClient, message: JoinedGroupEv):
    LOGS.info("JoinedGroupEv:")
    LOGS.info(message)
    # await on_message(client, message)


########### Start ############


async def start_bot():
    try:
        if len(sys.argv) != 3:
            await restore_wa_db()
        (
            await bot.client.PairPhone(conf.PH_NUMBER, show_push_notification=True)
            if conf.PH_NUMBER
            else await bot.client.connect()
        )
        await on_startup()
        await bot.client.idle()
    except Exception:
        LOGS.critical(traceback.format_exc())
        LOGS.critical("Cannot recover from error, exiting…")
        exit()


bot.client.loop.run_until_complete(start_bot())
