import pickle

from pymongo import MongoClient

from bot import LOGS, bot, conf, os, sys, version_file
from bot.utils.bot_utils import create_api_token
from bot.utils.local_db_utils import load_local_db
from bot.utils.os_utils import file_exists, is_executable_installed

LOGS.info("=" * 30)
LOGS.info(f"Python version: {sys.version.split()[0]}")

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

if not os.path.isdir("ytdl/"):
    os.mkdir("ytdl/")


LOGS.info("=" * 30)


def load_db(_db, _key, var, var_type=None):
    queries = _db.find({"_id": conf.PH_NUMBER or conf.DB_ID})
    raw = None
    for query in queries:
        raw = query.get(_key)

    if not raw:
        return
    out = pickle.loads(raw)
    if not out:
        return

    if var_type == "list":
        for item in out.split():
            if item in conf.OWNER.split():
                continue
            if item not in var:
                var.append(item)
    elif var_type == "dict":
        var.update(out)


if conf.DATABASE_URL:
    cluster = MongoClient(conf.DATABASE_URL)
    db = cluster[conf.DBNAME]
    rssdb = db["rss"]
    userdb = db["users"]
    nfdb = db["note_filter"]

    load_db(nfdb, "note", bot.notes_dict, "dict")
    load_db(nfdb, "filter", bot.filters_dict, "dict")
    load_db(rssdb, "rss", bot.rss_dict, "dict")
    load_db(userdb, "groups", bot.group_dict, "dict")
    load_db(userdb, "users", bot.user_dict, "dict")


else:
    rssdb = userdb = miscdb = nfdb = None

    load_local_db()

def check_for_pg_tools():
    if not conf.BACKUP_WA_DB:
        return
    if not (
        is_executable_installed("pg_dump")
        and is_executable_installed("pg_restore")
    ):
        LOGS.info("Either pg_dump or pg_restore was not found in PATH!")
        LOGS.info("Disabling WA Database Backup!")
    else:
        bot.pg_tools_are_installed = True

check_for_pg_tools()
create_api_token()

    