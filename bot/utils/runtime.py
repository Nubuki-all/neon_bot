from bot.config import bot
from bot.utils.msg_rank import save_msg_ranking
from bot.utils.msg_store import flush_messages


async def shutdown_services():
    await bot.client.disconnect()
    await bot.requests.close()
    bot.stop_back_up = True
    await bot.backup_wa_db()
    await save_msg_ranking()
    if bot.pending_saved_messages:
        if not bot.auto_save_msg_is_running:
            return
        await flush_messages()
