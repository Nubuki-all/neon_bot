import os
import pickle
import sqlite3
from contextlib import closing

from bot import LOGS, bot, local_db

# Pickle files used before the SQLite store; imported once, then kept as .bak
LEGACY_FILES = {
    "groups": ".local_groups.pkl",
    "note": ".local_notedb.pkl",
    "filter": ".local_filterdb.pkl",
    "rss": ".local_rssdb.pkl",
    "reminders": ".local_remdb.pkl",
    "users": ".local_users.pkl",
}


def stores() -> dict:
    """save2db2's db names and the dict each one holds"""
    return {
        "groups": bot.group_dict,
        "note": bot.notes_dict,
        "filter": bot.filters_dict,
        "rss": bot.rss_dict,
        "reminders": bot.remind_dict,
        "users": bot.user_dict,
    }


def connect():
    conn = sqlite3.connect(local_db, timeout=30)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS store (name TEXT PRIMARY KEY, data BLOB NOT NULL)"
    )
    return conn


def write(conn, name: str, p_data: bytes):
    conn.execute(
        "INSERT INTO store (name, data) VALUES (?, ?) "
        "ON CONFLICT(name) DO UPDATE SET data = excluded.data",
        (name, p_data),
    )


def import_legacy_files(conn):
    """Moves data from the old pickle files into the store, keeping the files as .bak"""
    found = [(n, p) for n, p in LEGACY_FILES.items() if os.path.exists(p)]
    if not found:
        return
    with conn:
        for name, path in found:
            # Already imported when a rename failed after the commit
            if conn.execute("SELECT 1 FROM store WHERE name = ?", (name,)).fetchone():
                continue
            with open(path, "rb") as file:
                write(conn, name, pickle.dumps(pickle.load(file)))
    for name, path in found:
        os.replace(path, path + ".bak")
        LOGS.info(f"Moved {path} into {local_db}; the old file is now {path}.bak")


def load_local_db():
    with closing(connect()) as conn:
        import_legacy_files(conn)
        rows = conn.execute("SELECT name, data FROM store").fetchall()
    known = stores()
    for name, p_data in rows:
        if name in known:
            known[name].update(pickle.loads(p_data))


def save2db_lcl2(db: str, p_data: bytes):
    """Saves an already pickled dict; pickling happens on the event loop, not here"""
    with closing(connect()) as conn, conn:
        write(conn, db, p_data)
