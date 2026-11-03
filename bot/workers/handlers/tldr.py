import httpx

from bot.config import conf
from bot.utils.bot_utils import LimitedDict, get_sha256
from bot.utils.log_utils import logger
from bot.utils.modal_utils import explain
from bot.utils.msg_utils import chat_is_allowed, user_is_allowed, user_is_privileged

# The model has a 16k token context; leave room for the prompt, the image
# and the reply
MAX_TEXT = 24000
# Same cap as upscale for downloading replied images
MAX_IMAGE_SIZE = 17939583
# Replies by (mode, text hash, image hash), so asking again about the same
# message doesn't wake the model up
tldr_cache = LimitedDict()


async def _explain_replied(event, mode: str, usage: str):
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        if not conf.MODAL_TLDR_API:
            return await event.reply("*This command is currently not available.*")
        replied = event.reply_to_message
        if not replied:
            return await event.reply(usage)
        text = (replied.caption or replied.text or "").strip()
        is_image = (
            replied.image
            or replied.sticker
            or (replied.document and replied.document.mimetype.startswith("image"))
        )
        if not (text or is_image):
            return await event.reply("*Reply to a text message or an image.*")
        if is_image and replied.media.fileLength > MAX_IMAGE_SIZE:
            return await event.reply("*Replied image is too large.*")
        text = text[:MAX_TEXT]
        key = (mode, get_sha256(text), replied.media.fileSHA256 if is_image else b"")
        if reply := tldr_cache.get(key):
            tldr_cache[key] = reply
            return await event.reply(reply)
        async with event.react("🧠"):
            image = await replied.download() if is_image else None
            reply = await explain(mode, text, image)
        if not reply:
            return await event.reply("*Got an empty reply, try again.*")
        tldr_cache[key] = reply
        await event.reply(reply)
    except httpx.HTTPError:
        await logger(Exception)
        await event.reply("*Couldn't reach the model, try again later.*")
    except Exception:
        await logger(Exception)
        await event.react("❌")


async def tldr(event, args, client):
    """
    Summarise the replied message: its text, an image (read with any text in
    it) or both. The first use after a while is slow, as the model starts up.
    """
    await _explain_replied(event, "tldr", tldr.__doc__)


async def eli5(event, args, client):
    """
    Explain the replied message in simple words: its text, an image (read with
    any text in it) or both. The first use after a while is slow, as the model
    starts up.
    """
    await _explain_replied(event, "eli5", eli5.__doc__)
