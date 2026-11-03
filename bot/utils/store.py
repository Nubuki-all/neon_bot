"""
Keeps the bot's dicts as one record per entry, in MongoDB or a local SQLite file.

Each dict is split into records: one per top-level key (a group, a user,
an RSS feed…), or per second-level key for notes and filters, whose
image notes could otherwise pass MongoDB's 16 MB document limit. Values
are stored with store_codec (plain data, no pickle). A save only writes
the records that changed and deletes the ones that are gone.

The old layout (each dict pickled whole into one document, or into
.local_*.pkl files) is imported once on first start; the old MongoDB
documents are left as they were, the .pkl files are renamed to .bak.
"""

import asyncio
import json
import os
import pickle
import sqlite3
from contextlib import closing

from bot import LOGS, bot, conf, local_db

from .bot_utils import sync_to_async
from .store_codec import decode, encode

VERSION = 1


def stores() -> dict:
    """save2db2's db names -> (the dict, how many key levels make a record)"""
    return {
        "groups": (bot.group_dict, 1),
        "users": (bot.user_dict, 1),
        "rss": (bot.rss_dict, 1),
        "reminders": (bot.remind_dict, 1),
        "gift": (bot.gift_dict, 1),
        "note": (bot.notes_dict, 2),
        "filter": (bot.filters_dict, 2),
    }


# Where each dict was kept before
LEGACY_MONGO = {
    "groups": "users",
    "users": "users",
    "rss": "rss",
    "gift": "rss",
    "note": "note_filter",
    "filter": "note_filter",
    "reminders": "reminders",
}
LEGACY_FILES = {
    "groups": ".local_groups.pkl",
    "users": ".local_users.pkl",
    "rss": ".local_rssdb.pkl",
    "gift": ".local_giftdb.pkl",
    "note": ".local_notedb.pkl",
    "filter": ".local_filterdb.pkl",
    "reminders": ".local_remdb.pkl",
}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def flatten(data: dict, depth: int) -> dict:
    records = {}
    for k1, v1 in data.items():
        if depth == 2 and isinstance(v1, dict) and v1:
            for k2, v2 in v1.items():
                records[(k1, k2)] = v2
        else:
            records[(k1,)] = v1
    return records


def unflatten(records: list, target: dict):
    # Whole entries first, so second-level records land inside them
    for key, value in sorted(records, key=lambda r: len(r[0])):
        if len(key) == 1:
            target[key[0]] = value
        else:
            target.setdefault(key[0], {})[key[1]] = value


class SQLiteBackend:
    def __init__(self, path: str):
        self.path = path

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS records "
            "(store TEXT, key TEXT, value TEXT NOT NULL, PRIMARY KEY (store, key))"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value TEXT)"
        )
        return conn

    def load(self, store: str) -> list:
        with closing(self.connect()) as conn:
            rows = conn.execute(
                "SELECT key, value FROM records WHERE store = ?", (store,)
            ).fetchall()
        return [(key, json.loads(value)) for key, value in rows]

    def write(self, store: str, upserts: dict, deletes: list):
        with closing(self.connect()) as conn, conn:
            conn.executemany(
                "INSERT INTO records (store, key, value) VALUES (?, ?, ?) "
                "ON CONFLICT (store, key) DO UPDATE SET value = excluded.value",
                [(store, k, json.dumps(v)) for k, v in upserts.items()],
            )
            conn.executemany(
                "DELETE FROM records WHERE store = ? AND key = ?",
                [(store, k) for k in deletes],
            )

    def version(self) -> int:
        with closing(self.connect()) as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE name = 'version'"
            ).fetchone()
        return int(row[0]) if row else 0

    def set_version(self, version: int):
        with closing(self.connect()) as conn, conn:
            conn.execute(
                "INSERT INTO meta (name, value) VALUES ('version', ?) "
                "ON CONFLICT (name) DO UPDATE SET value = excluded.value",
                (str(version),),
            )

    def legacy(self) -> dict:
        data = {}
        for name, path in LEGACY_FILES.items():
            if os.path.exists(path):
                with open(path, "rb") as file:
                    data[name] = pickle.load(file)
        return data

    def legacy_done(self):
        for path in LEGACY_FILES.values():
            if os.path.exists(path):
                os.replace(path, path + ".bak")
                LOGS.info(f"Imported {path} into {
                    self.path}; kept it as {path}.bak")


class MongoBackend:
    # Records of several bots can share a database; each is scoped by bot_id
    def __init__(self, db, bot_id: str):
        self.db = db
        self.bot_id = bot_id
        self.records = db["records"]
        self.meta = db["records_meta"]

    def _id(self, store: str, key: str) -> dict:
        # Field order matters for matching a document _id
        return {"bot": self.bot_id, "store": store, "key": key}

    def load(self, store: str) -> list:
        query = {"_id.bot": self.bot_id, "_id.store": store}
        return [(doc["_id"]["key"], doc["value"]) for doc in self.records.find(query)]

    def write(self, store: str, upserts: dict, deletes: list):
        from pymongo import DeleteOne, ReplaceOne

        ops = [
            ReplaceOne(
                {"_id": self._id(store, k)},
                {"_id": self._id(store, k), "value": v},
                upsert=True,
            )
            for k, v in upserts.items()
        ] + [DeleteOne({"_id": self._id(store, k)}) for k in deletes]
        if ops:
            self.records.bulk_write(ops, ordered=False)

    def version(self) -> int:
        doc = self.meta.find_one({"_id": self.bot_id})
        return doc.get("version", 0) if doc else 0

    def set_version(self, version: int):
        self.meta.update_one(
            {"_id": self.bot_id}, {"$set": {"version": version}}, upsert=True
        )

    def legacy(self) -> dict:
        data = {}
        for name, collection in LEGACY_MONGO.items():
            doc = self.db[collection].find_one({"_id": self.bot_id})
            if doc and doc.get(name):
                data[name] = pickle.loads(doc[name])
        return data

    def legacy_done(self):
        # The old documents are left untouched as a backup
        pass


class DataStore:
    def __init__(self, backend):
        self.backend = backend
        # Per store: record key -> canonical form of what's saved
        self.saved = {name: {} for name in stores()}
        self.locks = {}

    def encode_records(self, name: str, data: dict):
        """Encoded records of a dict, with the errors for records that can't be"""
        _, depth = stores()[name]
        encoded, errors = {}, []
        for key, value in flatten(data, depth).items():
            try:
                key_id = canonical(encode(list(key)))
                encoded[key_id] = encode(value, f"{name}{list(key)}")
            except TypeError as e:
                errors.append(e)
                # Keep what's saved for it rather than deleting it
                try:
                    key_id = canonical(encode(list(key)))
                except TypeError:
                    continue
                if key_id in self.saved[name]:
                    encoded[key_id] = None
        return encoded, errors

    def load(self):
        """Fills the bot's dicts from the store, importing the old layout first"""
        if self.backend.version() < VERSION:
            self.migrate()
            return
        for name, (target, _) in stores().items():
            records = []
            for key_id, value in self.backend.load(name):
                try:
                    records.append((tuple(decode(json.loads(key_id))), decode(value)))
                except Exception:
                    LOGS.exception(f"Skipping unreadable {name} record {key_id}")
                    continue
                self.saved[name][key_id] = canonical(value)
            unflatten(records, target)

    def migrate(self):
        legacy = self.backend.legacy()
        for name, data in legacy.items():
            target, _ = stores()[name]
            target.update(data)
            encoded, errors = self.encode_records(name, target)
            for e in errors:
                LOGS.error(f"Not migrated: {e}")
            upserts = {k: v for k, v in encoded.items() if v is not None}
            self.backend.write(name, upserts, [])
            self.saved[name] = {k: canonical(v) for k, v in upserts.items()}
        self.backend.set_version(VERSION)
        self.backend.legacy_done()
        if legacy:
            LOGS.info(f"Moved {', '.join(legacy)} to the new storage layout")

    async def save(self, name: str, data: dict):
        lock = self.locks.setdefault(name, asyncio.Lock())
        async with lock:
            # Encoded here, on the event loop, so the dict can't change
            # meanwhile
            encoded, errors = self.encode_records(name, data)
            saved = self.saved[name]
            upserts = {
                k: v
                for k, v in encoded.items()
                if v is not None and saved.get(k) != canonical(v)
            }
            deletes = [k for k in saved if k not in encoded]
            if upserts or deletes:
                await sync_to_async(self.backend.write, name, upserts, deletes)
            for k, v in upserts.items():
                saved[k] = canonical(v)
            for k in deletes:
                saved.pop(k, None)
        for e in errors:
            LOGS.error(f"Not saved: {e}")


def open_store() -> DataStore:
    if conf.DATABASE_URL:
        from pymongo import MongoClient

        db = MongoClient(conf.DATABASE_URL)[conf.DBNAME]
        backend = MongoBackend(db, conf.PH_NUMBER or conf.DB_ID)
    else:
        backend = SQLiteBackend(local_db)
    data_store = DataStore(backend)
    data_store.load()
    return data_store
