from bot.config import bot, conf
from bot.startup.before import data_store

from .log_utils import logger  # noqa  # pylint: disable=unused-import
from .os_utils import cpu_count, enshell, s_remove


async def save2db2(data: dict, db: str):
    """Saves a dict (bot.group_dict, "groups" etc.); only changed entries are written"""
    await data_store.save(db, data)


async def backup_wa_db():
    if not conf.BACKUP_WA_DB:
        return
    if not bot.pg_tools_are_installed:
        return
    back_up_file = "psql/backup.dump"
    cmd = [
        "pg_dump",
        f"--dbname={conf.WA_DB}",
        "-Fd",
        f"-j {cpu_count}",
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
    # await logger(e=f"{stdout}\n\n{stderr}")

    cmd = [
        "pg_restore",
        "--no-owner",
        "-j",
        f"{cpu_count}",
        "--clean",
        "--if-exists",
        "-x",
        "--disable-triggers",  # Disable foreign key checks during data restore
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
    # await logger(e=f"{stdout}\n\n{stderr}")
    s_remove(back_up_file, folders=True)


async def restore_wa_db():
    if not conf.BACKUP_WA_DB:
        return
    if not bot.pg_tools_are_installed:
        return
    restore_file = "psql/restore.dump"
    cmd = [
        "pg_dump",
        f"--dbname={conf.BACKUP_WA_DB}",
        "-Fd",
        f"-j {cpu_count}",
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
    # await logger(e=f"{stdout}\n\n{stderr}")

    cmd = [
        "pg_restore",
        "--no-owner",
        "-j",
        f"{cpu_count}",
        "--clean",
        "--if-exists",
        "--disable-triggers",  # Disable foreign key checks during data restore
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
    # await logger(e=f"{stdout}\n\n{stderr}")
    s_remove(restore_file, folders=True)


bot.backup_wa_db = backup_wa_db
