import asyncio

from neonize.utils.message import get_poll_update_message

from bot import sudo_btn_lock
from bot.config import bot

from .bot_utils import get_sha256, trunc_string

active_poll_dict = {}


async def poll_as_button_handler(event):
    async with sudo_btn_lock:
        poll_update = get_poll_update_message(event.message)
        poll_msg_key = poll_update.pollCreationMessageKey
        if poll_msg_key.fromMe:
            return
        if not (poll_info := active_poll_dict.get(poll_msg_key.ID)):
            return
        if poll_info.get("user") != event.from_user.id:
            return
        selected = await bot.client.decrypt_poll_vote(event.message)
        if (conf_btn := poll_info.get("conf_btn")) and conf_btn not in [
            s.hex() for s in selected.selectedOptions
        ]:
            return
        poll_info.update(selected=selected)


async def create_sudo_button(
    name: str,
    options: dict,
    chat_jid,
    user_id: str,
    selectable: int = 1,
    conf_btn: str | None = None,
):
    async with sudo_btn_lock:
        poll_msg = await bot.client.build_poll_vote_creation(
            trunc_string(name, 255),
            [trunc_string(v[0], 100) for v in options.values()],
            selectable,
        )
        msg = await bot.client.send_message(chat_jid, poll_msg)
        poll_info = {}
        for key, value in options.items():
            poll_info.update({get_sha256(trunc_string(value[0], 100)): key})
        poll_info.update(user=user_id)
        if conf_btn and selectable > 1:
            poll_info.update({"conf_btn": get_sha256(trunc_string(conf_btn))})
        active_poll_dict.update({msg.ID: poll_info})
        return poll_msg, msg.ID


async def wait_for_button_response(msg_id: str, grace=0.1):
    while True:
        await asyncio.sleep(grace)
        async with sudo_btn_lock:
            poll_info = active_poll_dict.get(msg_id)
            if not poll_info:
                return
            if selected := poll_info.get("selected"):
                active_poll_dict.pop(msg_id)
                return [poll_info.get(s.hex()) for s in selected.selectedOptions]
