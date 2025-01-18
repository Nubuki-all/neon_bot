from pymongo.errors import ServerSelectionTimeoutError

from bot import asyncio
from bot.config import conf
from bot.startup.before import nfdb, pickle, rssdb, userdb

from .bot_utils import sync_to_async
from .local_db_utils import save2db_lcl2

# i suck at using database -_-' (#3)
# But hey if it works don't touch it
# wanna fix this?
# PRs are welcome

_filter = {"_id": conf.PH_NUMBER}

database = conf.DATABASE_URL
db_cluster = {
    "note": nfdb,
    "rss": rssdb,
    "users": userdb,
    "groups": userdb,
}


async def save2db(db, update, retries=3):
    while retries:
        try:
            await sync_to_async(db.update_one, _filter, {"$set": update}, upsert=True)
            break
        except ServerSelectionTimeoutError as e:
            retries -= 1
            if not retries:
                raise e
            await asyncio.sleep(0.5)


async def save2db2(data: dict | str, db: str):
    if not database:
        return await sync_to_async(save2db_lcl2, db)
    p_data = pickle.dumps(data)
    _update = {db: p_data}
    await save2db(db_cluster.get(db), _update)
