from importlib.metadata import version

from bot import LOGS, bot, conf, os, sys, version_file
from bot.utils.bot_utils import create_api_token
from bot.utils.os_utils import file_exists, is_executable_installed
from bot.utils.store import open_store

LOGS.info("=" * 30)
LOGS.info(f"Python version: {sys.version.split()[0]}")
LOGS.info(f"Neonize version: {version('neonize')}")

vmsg = f"Warning: {version_file} is missing!"
if file_exists(version_file):
    with open(version_file, "r") as file:
        ver = file.read().strip()
    vmsg = f"Bot version: {ver}"

LOGS.info(f"Branch: {bot.repo_branch or 'Unknown!'}")
LOGS.info(vmsg)

if os.path.isdir("/neon"):
    bot.docker_deployed = True
    LOGS.info("Docker: Yes")


LOGS.info("=" * 30)


# Fills the bot's dicts; save2db2 saves through it
data_store = open_store()


def check_for_pg_tools():
    if not conf.BACKUP_WA_DB:
        return
    if not (
        is_executable_installed("pg_dump") and is_executable_installed("pg_restore")
    ):
        LOGS.info("Either pg_dump or pg_restore was not found in PATH!")
        LOGS.info("Disabling WA Database Backup!")
    else:
        bot.pg_tools_are_installed = True


check_for_pg_tools()
create_api_token()
