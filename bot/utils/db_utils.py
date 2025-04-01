from pymongo.errors import ServerSelectionTimeoutError

from bot import asyncio
from bot.config import bot, conf
from bot.startup.before import nfdb, pickle, rssdb, userdb

from .bot_utils import sync_to_async
from .local_db_utils import save2db_lcl2
from .log_utils import logger
from .os_utils import cpu_count, enshell, s_remove

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


async def backup_wa_db():
    if not conf.BACKUP_WA_DB and conf.WA_DB:
        return
    back_up_file = "psql/backup.dump"
    cmd = [
        "pg_dump",
        f"--dbname={conf.WA_DB}",
        "-Fd",
        f"-j {cpu_count()}",
        "-f",
        back_up_file,
        "-v",
    ]
    process, stdout, stderr = await enshell(cmd)

    if process.returncode != 0:
        raise RuntimeError(
            # type: ignore
            f"stderr: {stderr} Return code: {process.returncode}"
        )
    # Debug:
    await logger(e=f"{stdout}\n\n{stderr}")

    cmd = [
        "pg_restore",
        "--no-owner",
        f"-j {cpu_count()}",
        "--clean",
        "--if-exists",
        "-x",
        f"--dbname={conf.BACKUP_WA_DB}",
        "-v",
        back_up_file,
    ]
    process, stdout, stderr = await enshell(cmd)

    if process.returncode != 0:
        raise RuntimeError(
            # type: ignore
            f"stderr: {stderr} Return code: {process.returncode}"
        )
    # Debug:
    await logger(e=f"{stdout}\n\n{stderr}")
    s_remove(back_up_file, folders=True)


async def restore_wa_db():
    if not conf.BACKUP_WA_DB and conf.WA_DB:
        return
    restore_file = "psql/restore.dump"
    cmd = [
        "pg_dump",
        f"--dbname={conf.BACKUP_WA_DB}",
        "-Fd",
        f"-j {cpu_count()}",
        "-f",
        restore_file,
        "-v",
    ]
    process, stdout, stderr = await enshell(cmd)

    if process.returncode != 0:
        raise RuntimeError(
            # type: ignore
            f"stderr: {stderr} Return code: {process.returncode}"
        )
    # Debug:
    await logger(e=f"{stdout}\n\n{stderr}")

    cmd = [
        "pg_restore",
        "--no-owner",
        f"-j {cpu_count()}",
        "--clean",
        "--if-exists",
        "-x",
        f"--dbname={conf.WA_DB}",
        "-v",
        restore_file,
    ]
    process, stdout, stderr = await enshell(cmd)

    if process.returncode != 0:
        raise RuntimeError(
            # type: ignore
            f"stderr: {stderr} Return code: {process.returncode}"
        )
    # Debug:
    await logger(e=f"{stdout}\n\n{stderr}")
    s_remove(restore_file, folders=True)


bot.backup_wa_db = backup_wa_db
