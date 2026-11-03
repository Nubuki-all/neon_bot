"""
Tries the storage migration on a copy of the bot's data, without touching it.

Run it inside the bot's container, from the bot's folder (so it finds .env),
pointing --repo at a checkout of the new storage code:

    git clone --depth 1 -b feat/sqlite-local-db https://github.com/Nubuki-all/neon_bot /tmp/neon-pr17
    cd /bot
    python3 /tmp/neon-pr17/scripts/check_storage_migration.py --repo /tmp/neon-pr17

With DATABASE_URL set, this bot's old documents are copied into a separate
test database on the same server (DBNAME + "_migration_test" by default),
migrated there, loaded back and compared with the original data. Without it,
the .local_*.pkl files are copied into a temporary folder and tested there.
The real database and files are only read.

The report shows counts, sizes and the positions of any differences, never
stored values. Keys (user ids, note names...) are hidden unless --show-keys.
"""

import argparse
import asyncio
import hashlib
import importlib.util
import logging
import os
import pickle
import re
import shutil
import sys
import tempfile
import time
import types
from types import SimpleNamespace as NS

from decouple import AutoConfig

LEGACY_FILES = {
    "groups": ".local_groups.pkl",
    "users": ".local_users.pkl",
    "rss": ".local_rssdb.pkl",
    "gift": ".local_giftdb.pkl",
    "note": ".local_notedb.pkl",
    "filter": ".local_filterdb.pkl",
    "reminders": ".local_remdb.pkl",
}


class Logs(logging.Handler):
    def __init__(self):
        super().__init__()
        self.errors = []

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            self.errors.append(record.getMessage())


def fresh_bot():
    return NS(
        group_dict={},
        user_dict={},
        rss_dict={},
        remind_dict={},
        notes_dict={},
        filters_dict={},
        gift_dict={"codes": [], "chats": []},
    )


def load_store_modules(repo, botobj, conf, local_db, logs):
    """store.py and store_codec.py from the checkout, without importing the bot itself"""
    log = logging.getLogger("storage-check")
    if logs not in log.handlers:
        log.addHandler(logs)
    log.setLevel(logging.INFO)
    mod = types.ModuleType("bot")
    mod.LOGS, mod.bot, mod.conf, mod.local_db = log, botobj, conf, local_db
    utils = types.ModuleType("bot.utils")
    utils.__path__ = []
    bot_utils = types.ModuleType("bot.utils.bot_utils")

    async def sync_to_async(func, *args, **kwargs):
        return func(*args, **kwargs)

    bot_utils.sync_to_async = sync_to_async
    sys.modules.update(
        {"bot": mod, "bot.utils": utils, "bot.utils.bot_utils": bot_utils}
    )
    loaded = {}
    for name in ("store_codec", "store"):
        spec = importlib.util.spec_from_file_location(
            f"bot.utils.{name}", os.path.join(repo, "bot", "utils", f"{name}.py")
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    return loaded["store"]


class Redactor:
    def __init__(self, show):
        self.show = show

    def key(self, key):
        if self.show:
            return repr(key)
        digest = hashlib.sha1(repr(key).encode()).hexdigest()[:6]
        return f"<{type(key).__name__}:{digest}>"


def differences(expected, actual, path, redact, out, limit=20):
    if len(out) >= limit:
        return
    if type(expected) is not type(actual):
        out.append(f"{path}: {type(expected).__name__} became {type(actual).__name__}")
    elif isinstance(expected, dict):
        for k in expected.keys() - actual.keys():
            out.append(f"{path}[{redact.key(k)}]: missing after migration")
        for k in actual.keys() - expected.keys():
            out.append(f"{path}[{redact.key(k)}]: appeared after migration")
        for k in expected.keys() & actual.keys():
            differences(
                expected[k], actual[k], f"{path}[{redact.key(k)}]", redact, out, limit
            )
    elif isinstance(expected, (list, tuple)):
        if len(expected) != len(actual):
            out.append(f"{path}: length {len(expected)} became {len(actual)}")
        else:
            for i, (e, a) in enumerate(zip(expected, actual)):
                differences(e, a, f"{path}[{i}]", redact, out, limit)
    elif expected != actual:
        out.append(f"{path}: {type(expected).__name__} value changed")


def stores_of(botobj):
    return {
        "groups": botobj.group_dict,
        "users": botobj.user_dict,
        "rss": botobj.rss_dict,
        "reminders": botobj.remind_dict,
        "gift": botobj.gift_dict,
        "note": botobj.notes_dict,
        "filter": botobj.filters_dict,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--repo", required=True, help="checkout with the new storage code"
    )
    parser.add_argument(
        "--test-db", help="test database name (default: DBNAME_migration_test)"
    )
    parser.add_argument(
        "--keep", action="store_true", help="keep the test database afterwards"
    )
    parser.add_argument(
        "--show-keys", action="store_true", help="show keys in the report"
    )
    args = parser.parse_args()

    env = AutoConfig(search_path=os.getcwd())
    url = env("DATABASE_URL", default=None)
    dbname = env("DBNAME", default="Neon")
    bot_id = env("PH_NUMBER", default="") or env("DB_ID", default="0000")
    conf = NS(DATABASE_URL=url, DBNAME=dbname, PH_NUMBER=bot_id, DB_ID=bot_id)
    redact = Redactor(args.show_keys)
    logs = Logs()

    tmp = tempfile.mkdtemp(prefix="storage-check-")
    cleanup = []
    try:
        if url:
            from pymongo import MongoClient

            test_name = args.test_db or f"{dbname}_migration_test"
            if test_name == dbname:
                sys.exit("--test-db must differ from DBNAME")
            client = MongoClient(url)
            source, test = client[dbname], client[test_name]
            if test.list_collection_names():
                sys.exit(
                    f"Test database {test_name} isn't empty; drop it or pick another --test-db"
                )
            print(f"Copying this bot's old documents from {dbname} to {test_name}…")
            store_mod = load_store_modules(args.repo, fresh_bot(), conf, None, logs)
            expected = {}
            for collection in sorted(set(store_mod.LEGACY_MONGO.values())):
                doc = source[collection].find_one({"_id": bot_id})
                if doc:
                    test[collection].insert_one(doc)
            for name, collection in store_mod.LEGACY_MONGO.items():
                doc = source[collection].find_one({"_id": bot_id})
                if doc and doc.get(name):
                    expected[name] = pickle.loads(doc[name])
            if not args.keep:
                cleanup.append(lambda: client.drop_database(test_name))

            def open_backend(store_mod):
                return store_mod.MongoBackend(test, bot_id)

            def record_sizes(store_mod):
                import bson

                sizes = {}
                for doc in test["records"].find({"_id.bot": bot_id}):
                    store = doc["_id"]["store"]
                    count, largest = sizes.get(store, (0, 0))
                    sizes[store] = (count + 1, max(largest, len(bson.encode(doc))))
                return sizes

        else:
            print(f"No DATABASE_URL; copying the .local_*.pkl files to {tmp}…")
            expected = {}
            for name, path in LEGACY_FILES.items():
                if os.path.exists(path):
                    shutil.copy2(path, os.path.join(tmp, path))
                    with open(path, "rb") as file:
                        expected[name] = pickle.load(file)
            os.chdir(tmp)

            def open_backend(store_mod):
                return store_mod.SQLiteBackend(os.path.join(tmp, ".local.db"))

            def record_sizes(store_mod):
                import sqlite3

                sizes = {}
                with sqlite3.connect(os.path.join(tmp, ".local.db")) as conn:
                    for store, size in conn.execute(
                        "SELECT store, length(value) FROM records"
                    ):
                        count, largest = sizes.get(store, (0, 0))
                        sizes[store] = (count + 1, max(largest, size))
                return sizes

        if not expected:
            sys.exit("Found no old data for this bot; nothing to test.")
        print(f"Old data found for: {', '.join(sorted(expected))}")

        # 1. Migrate, as the first start on the new code would
        started = time.time()
        migrated = fresh_bot()
        store_mod = load_store_modules(args.repo, migrated, conf, None, logs)
        store_mod.DataStore(open_backend(store_mod)).load()
        print(f"Migrated in {time.time() - started:.1f}s")

        # 2. Load again, as every later start would
        loaded = fresh_bot()
        store_mod = load_store_modules(args.repo, loaded, conf, None, logs)
        data_store = store_mod.DataStore(open_backend(store_mod))
        data_store.load()

        # 3. Saving unchanged data must write nothing (stores without old data,
        # like gift's defaults, are written on their first save; that's expected)
        writes = []
        write = data_store.backend.write
        data_store.backend.write = lambda s, up, de: (
            writes.append((s, len(up), len(de))),
            write(s, up, de),
        )[1]

        async def save_all():
            for name, data in stores_of(loaded).items():
                await data_store.save(name, data)

        asyncio.run(save_all())

        sizes = record_sizes(store_mod)
        print("\nStore       records  largest record")
        problems = 0
        for name in stores_of(loaded):
            count, largest = sizes.get(name, (0, 0))
            warn = (
                "  <- close to MongoDB's 16 MB limit"
                if largest > 12 * 1024 * 1024
                else ""
            )
            print(f"{name:<10} {count:>8}  {largest / 1024:>10.1f} KB{warn}")
        print()
        for name, data in expected.items():
            found = []
            differences(data, stores_of(loaded)[name], name, redact, found)
            if found:
                problems += len(found)
                print(
                    f"{name}: {len(found)} difference(s)"
                    + (" (first 20)" if len(found) >= 20 else "")
                )
                for line in found:
                    print(f"  {line}")
            else:
                print(f"{name}: identical after migration and reload")
        writes = [w for w in writes if w[0] in expected]
        if writes:
            problems += 1
            print(f"\nSaving unchanged data wrote records: {writes}")
        else:
            print("\nSaving unchanged data wrote nothing, as it should")
        if logs.errors:
            problems += len(logs.errors)
            print(f"\n{len(logs.errors)} error(s) logged:")
            for line in logs.errors[:20]:
                # Error messages name positions, which can include ids
                print(
                    f"  {line if args.show_keys else re.sub(r'[0-9]{6,}', '<id>', line)}"
                )
        print(
            f"\n{'No problems found.' if not problems else f'{problems} problem(s) found.'}"
        )
        if url and args.keep:
            print(f"Kept the test database {test_name}.")
    finally:
        for step in cleanup:
            step()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
