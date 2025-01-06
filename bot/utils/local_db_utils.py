import pickle

from bot import bot, local_budb, local_ndb, local_rdb

from .bot_utils import list_to_str
from .os_utils import file_exists


def load_local_db():
    if file_exists(local_rdb):
        with open(local_rdb, "rb") as file:
            local_dict = pickle.load(file)
        bot.rss_dict.update(local_dict)

    if file_exists(local_ndb):
        with open(local_ndb, "rb") as file:
            local_dict = pickle.load(file)
        bot.notes_dict.update(local_dict)

    if file_exists(local_budb):
        with open(local_budb, "rb") as file:
            local_b_users = pickle.load(file)
        for user in local_b_users:
            if user not in bot.banned:
                bot.banned.append(user)


def save2db_lcl2(db):
    if db is None:
        with open(local_budb, "wb") as file:
            pickle.dump(list_to_str(bot.banned), file)
    elif db == "rss":
        with open(local_rdb, "wb") as file:
            pickle.dump(bot.rss_dict, file)
    elif db == "note":
        with open(local_ndb, "wb") as file:
            pickle.dump(bot.notes_dict, file)
