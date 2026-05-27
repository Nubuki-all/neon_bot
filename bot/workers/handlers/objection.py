import asyncio
import os
import shutil
import time
from objection_engine.beans.comment import Comment
from objection_engine.renderer import render_comment_list

from bot import bot, heavy_proc_lock, conf
from bot.utils.log_utils import logger
from bot.utils.msg_store import get_messages_between

objection_sessions = {}

async def insession(event, args, client):
    """
    Starts an objection session by marking the current message (or the replied message) as the starting point.
    Usage: /insession
    """
    chat_id = event.chat.id
    start_msg_id = event.reply_to_message.id if event.reply_to_message else event.id

    objection_sessions[chat_id] = {
        "start_id": start_msg_id,
        "time": time.time()
    }

    await event.reply(
        f"Objection session started from message ID: `{start_msg_id}`.\n"
        f"Reply to the ending message with `{conf.CMD_PREFIX}renderobj` to generate the video.\n"
        "Session expires in 300 seconds."
    )

async def render_objection(event, args, client):
    """
    Renders the objection video for the messages between the start point and the replied message.
    Usage: /renderobj (replying to the end message)
    """
    chat_id = event.chat.id
    session = objection_sessions.get(chat_id)

    if not session:
        return await event.reply(f"No active objection session in this chat. Start one with `{conf.CMD_PREFIX}insession`.")

    if time.time() - session["time"] > 300:
        del objection_sessions[chat_id]
        return await event.reply(f"Objection session timed out. Start a new one with `{conf.CMD_PREFIX}insession`.")

    end_msg_id = event.reply_to_message.id if event.reply_to_message else event.id
    start_id = session["start_id"]

    del objection_sessions[chat_id]

    async with event.react("🎬"):
        try:
            messages = await get_messages_between(chat_id, start_id, end_msg_id)
            if not messages:
                return await event.reply("No messages found in the specified range.")

            comments = []
            temp_dir = f"temp_objection_{chat_id}_{int(time.time())}"
            os.makedirs(temp_dir, exist_ok=True)

            for msg in messages:
                is_image = msg.image or (msg.document and msg.document.mimetype.startswith("image"))
                if not (msg.text or is_image):
                    continue

                user_name = msg.from_user.name or "User"
                user_id = msg.from_user.id
                text = msg.text or msg.caption or "..."
                evidence_path = None

                if is_image:
                    img_path = os.path.join(temp_dir, f"evidence_{msg.id}.jpg")
                    await msg.download(img_path)
                    evidence_path = img_path

                comments.append(Comment(
                    user_id=user_id,
                    user_name=user_name,
                    text_content=text,
                    evidence_path=evidence_path
                ))

            if not comments:
                return await event.reply("No valid text or image messages found in the range.")

            output_file = os.path.join(temp_dir, "objection_video.mp4")

            async with heavy_proc_lock:
                # render_comment_list is likely synchronous and heavy
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: render_comment_list(comments, output_filename=output_file)
                )

            if os.path.exists(output_file):
                await event.reply_video(output_file, caption="Here is your objection video!")
            else:
                await event.reply("Failed to generate objection video.")

        except Exception as e:
            await logger(e)
            await event.reply(f"An error occurred: {e}")
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
