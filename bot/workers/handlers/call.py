import inspect
import tempfile

from neonize.exc import CallError
from yt_dlp import YoutubeDL

from bot import bot
from bot.utils.bot_utils import sync_to_async
from bot.utils.log_utils import logger
from bot.utils.msg_utils import user_is_privileged
from bot.utils.os_utils import s_remove
from bot.utils.ytdl_utils import is_supported


def forget_call(chat_id: str) -> dict | None:
    call = bot.calls.pop(chat_id, None)
    if call and call["file"]:
        s_remove(call["file"])
    return call


def download_audio(url: str) -> str:
    options = {
        "format": "bestaudio/best",
        "outtmpl": tempfile.mktemp(prefix="call_") + ".%(ext)s",
        "noplaylist": True,
        "cookiefile": ".cookies.txt",
        "quiet": True,
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


async def start_call(event) -> dict:
    chat = event.chat
    if chat.is_group:
        call_id = await bot.client.call_group(chat.jid)
    else:
        call_id = await bot.client.call_user(chat.jid)
    call = bot.calls[chat.id] = {"id": call_id, "jid": chat.jid, "file": None}
    return call


async def call_play(event, args, client):
    """
    [Owner | Sudo] Play audio into a voice call in this chat (for testing calls).
    Starts a call if there isn't one; in a group that rings every member (at most 31).
    Playing again replaces the current audio. Hang up with endcall.

    Arguments:
        Reply to an audio, voice note or video, or
        link - a direct media link or any link yt-dlp supports
    """
    if not user_is_privileged(event.from_user.id):
        return
    if not bot.client.enable_calls:
        return await event.reply(
            "Calls are disabled. Set ENABLE_CALLS=True and restart."
        )
    replied = event.reply_to_message
    url = args.strip()
    if not (url or (replied and (replied.audio or replied.video or replied.ptv))):
        return await event.reply(f"{inspect.getdoc(call_play)}")
    status = await event.reply("Preparing audio…")
    file = None
    try:
        if url:
            if is_supported(url):
                file = await sync_to_async(download_audio, url)
            source = file or url
        else:
            file = source = tempfile.mktemp(prefix="call_")
            await replied.download(file)

        call = bot.calls.get(event.chat.id) or await start_call(event)
        try:
            await bot.client.call_play(call["id"], source)
        except CallError:
            # the call ended without us hearing about it; start a new one
            forget_call(event.chat.id)
            call = await start_call(event)
            await bot.client.call_play(call["id"], source)
        if call["file"] and call["file"] != file:
            s_remove(call["file"])
        call["file"] = file
        await status.edit("Playing in the call.")
    except CallError as e:
        if file:
            s_remove(file)
        await status.edit(f"Call failed: {e}")
    except Exception:
        if file:
            s_remove(file)
        await logger(Exception)
        await status.edit("`An error occurred.`")


async def call_end(event, args, client):
    """
    [Owner | Sudo] Hang up the voice call in this chat.
    """
    if not user_is_privileged(event.from_user.id):
        return
    call = forget_call(event.chat.id)
    if not call:
        return await event.reply("There's no call in this chat.")
    try:
        await bot.client.call_hangup(call["id"])
    except CallError:
        pass
    await event.reply("Hung up.")


async def on_call_ended(ev):
    for chat_id, call in list(bot.calls.items()):
        if call["id"] == ev.CallID:
            forget_call(chat_id)
            await bot.client.send_message(
                call["jid"], f"Call ended ({ev.Reason or 'no reason'})."
            )


async def on_playback_finished(ev):
    for call in list(bot.calls.values()):
        if call["id"] == ev.CallID:
            await bot.client.send_message(call["jid"], "Finished playing.")
