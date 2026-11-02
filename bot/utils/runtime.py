from bot.config import bot
from bot.utils.msg_store import flush_messages
from bot.workers.handlers.genshin import stop_genshin_watcher


async def shutdown_services():
    await stop_genshin_watcher()
    await bot.client.disconnect()
    await bot.requests.close()
    bot.stop_back_up = True
    await bot.backup_wa_db()
    if bot.pending_saved_messages:
        if not bot.auto_save_msg_is_running:
            return
        bot.msg_leaderboard_counter = 100
        await flush_messages()
