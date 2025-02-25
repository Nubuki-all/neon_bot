import asyncio
from bot import client, sudo_btn_lock
from neonize.utils.message import get_poll_update_message

from .bot_utils import get_sha256

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
        selected = await client.decrypt_poll_vote(event.message)
        poll_info.update(selected=selected)


async def create_sudo_button(name:str, options:dict, chat_jid, user_id: str, selectable: int = 1):
    async with sudo_btn_lock:
        poll_msg = await client.build_poll_vote_creation(name, [v[0] for v in options.values()], selectable)
        msg = await client.send_message(chat_jid, poll_msg)
        poll_info = {}
        for key, value in options.items():
            poll_info.update({sha256(value[0]): key})
        poll_info.update(user=user_id)
        active_poll_dict.update({msg.ID: poll_info})
        return poll_msg, msg.ID


async def wait_for_button_response(msg_id:str, grace=0.1):
    while True:
        await asyncio.sleep(grace)
        async with sudo_btn_lock:
            poll_info = active_poll_dict.get(msg_id)
            if not poll_info:
                return 
            if (selected := poll_info.get("selected")):
                return [poll_info.get(s) for s in selected]
            
    