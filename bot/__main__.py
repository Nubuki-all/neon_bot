from bot.utils.os_utils import re_x, s_remove

from . import (
    LOGS,
    ConnectedEv,
    DisconnectedEv,
    GroupInfoEv,
    JoinedGroupEv,
    LoggedOutEv,
    MessageEv,
    NewAClient,
    asyncio,
    bot,
    con_ind,
    conf,
    time,
    traceback,
)
from .startup.after import on_startup
from .utils.msg_utils import Event, event_handler, on_message
from .utils.os_utils import file_exists, re_x, s_remove
from .workers.handlers.afk import activate_afk, afk_helper
from .workers.handlers.ani import airing, anime
from .workers.handlers.dev import bash, eval_message, get_logs
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
from .workers.handlers.stuff import gc_info, getcmds, getmeme, hello, up
from .workers.handlers.wa import (
    delete_notes,
    gc_handler,
    get_notes,
    get_notes2,
    msg_ranking,
    pick_random,
    rec_msg_ranking,
    sanitize_url,
    save_notes,
    sticker_reply,
    stickerize_image,
    tag_all_admins,
    tag_all_owners,
    tag_all_sudoers,
    tag_everyone,
    test_button,
    upscale_image,
)
from .workers.handlers.yt import youtube_reply


@bot.client.event(ConnectedEv)
async def on_connected(_: NewAClient, __: ConnectedEv):
    LOGS.info("Bot has started.")


@bot.client.event(LoggedOutEv)
async def on_logout(_: NewAClient, __: LoggedOutEv):
    s_remove(con_ind)
    LOGS.info("Bot has been logged out.")
    LOGS.info("Restarting…")
    time.sleep(10)
    re_x()


@bot.client.event(DisconnectedEv)
async def _(_: NewAClient, __: DisconnectedEv):
    if not file_exists(con_ind):
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


@bot.register("cmds")
async def _(client: NewAClient, message: Event):
    await event_handler(message, getcmds)


@bot.register("msg_ranking")
async def _(client: NewAClient, message: Event):
    await event_handler(message, msg_ranking, bot.client)


@bot.register("save")
async def _(client: NewAClient, message: Event):
    await event_handler(message, save_notes, require_args=True)


@bot.register("get")
async def _(client: NewAClient, message: Event):
    await event_handler(message, get_notes)


@bot.register("del_note")
async def _(client: NewAClient, message: Event):
    await event_handler(message, delete_notes, require_args=True)


@bot.register("afk")
async def _(client: NewAClient, message: Event):
    await event_handler(message, activate_afk)


@bot.register("sanitize")
async def _(client: NewAClient, message: Event):
    await event_handler(message, sanitize_url)


@bot.register("sticker")
async def _(client: NewAClient, message: Event):
    await event_handler(message, stickerize_image)


@bot.register("random")
async def _(client: NewAClient, message: Event):
    await event_handler(message, pick_random)


@bot.register("upscale")
async def _(client: NewAClient, message: Event):
    await event_handler(message, upscale_image)


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


@bot.register("button")
async def _(client: NewAClient, message: Event):
    await event_handler(message, test_button)


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await sticker_reply(message, None, client)


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await tag_all_admins(message, None, client)


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await tag_all_owners(message, None, client)


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await tag_all_sudoers(message, None, client)


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await tag_everyone(message, None, client)


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await get_notes2(message, None, client)


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await youtube_reply(message, None, client)


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await afk_helper(message, None, client)


@bot.register(None)
async def _(client: NewAClient, message: Event):
    await rec_msg_ranking(message, None, client)


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

try:
    bot.loop = asyncio.get_event_loop()
    bot.loop.create_task(on_startup())
    if not bot.initialized_client:
        bot.loop.run_until_complete(
            bot.client.PairPhone(conf.PH_NUMBER, show_push_notification=True)
        )
    else:
        bot.loop.run_until_complete(bot.client.connect())
except Exception:
    LOGS.critical(traceback.format_exc())
    LOGS.critical("Cannot recover from error, exiting…")
    exit()
