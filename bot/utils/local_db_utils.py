import pickle

from bot import bot, local_fdb, local_gcdb, local_ndb, local_rdb, local_remdb, local_udb

from .os_utils import file_exists


def load_local_db():
    if file_exists(local_gcdb):
        with open(local_gcdb, "rb") as file:
            local_dict = pickle.load(file)
        bot.group_dict.update(local_dict)

    if file_exists(local_ndb):
        with open(local_ndb, "rb") as file:
            local_dict = pickle.load(file)
        bot.notes_dict.update(local_dict)

    if file_exists(local_fdb):
        with open(local_fdb, "rb") as file:
            local_dict = pickle.load(file)
        bot.filters_dict.update(local_dict)

    if file_exists(local_rdb):
        with open(local_rdb, "rb") as file:
            local_dict = pickle.load(file)
        bot.rss_dict.update(local_dict)

    if file_exists(local_remdb):
        with open(local_remdb, "rb") as file:
            local_dict = pickle.load(file)
        bot.remind_dict.update(local_dict)

    if file_exists(local_udb):
        with open(local_udb, "rb") as file:
            local_dict = pickle.load(file)
        bot.user_dict.update(local_dict)


def save2db_lcl2(db):
    if db == "groups":
        with open(local_gcdb, "wb") as file:
            pickle.dump(bot.group_dict, file)
    elif db == "note":
        with open(local_ndb, "wb") as file:
            pickle.dump(bot.notes_dict, file)
    elif db == "filter":
        with open(local_fdb, "wb") as file:
            pickle.dump(bot.filters_dict, file)
    elif db == "rss":
        with open(local_rdb, "wb") as file:
            pickle.dump(bot.rss_dict, file)
    elif db == "reminders":
        with open(local_remdb, "wb") as file:
            pickle.dump(bot.remind_dict, file)
    elif db == "users":
        with open(local_udb, "wb") as file:
            pickle.dump(bot.user_dict, file)
