#    This file is part of the neon_bot distribution.
#    Copyright (c) 2024 Nubuki-all
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3.
#
#    This program is distributed in the hope that it will be useful, but
#    WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#    General Public License for more details.
#
# License can be found in <
# https://github.com/Nubuki-all/neon_bot/blob/WA/License> .
import traceback

from decouple import config


class Config:
    def __init__(self):
        try:
            self.ALWAYS_DEPLOY_LATEST = config(
                "ALWAYS_DEPLOY_LATEST", default=False, cast=bool
            )
            self.ALLOWED_CHATS = config("ALLOWED_CHATS", default="")
            self.BANNED_USERS = config(
                "BANNED_USERS",
                default=str(),
            )
            self.BLOCK_NSFW = config("BLOCK_NSFW", default=True, cast=bool)
            self.DISABLE_CIP = config("DISABLE_CIP", default=False, cast=bool)
            self.PH_NUMBER = config("PH_NUMBER", default="")

            self.CMD_PREFIX = config("CMD_PREFIX", default="")
            self.DATABASE_URL = config("DATABASE_URL", default=None)
            self.DBNAME = config("DBNAME", default="Neon")
            self.DEBUG = config("DEBUG", default=False, cast=bool)
            self.DEV = config("DEV", default=0, cast=str)
            self.DYNO = config("DYNO", default=None)
            self.IGNORE_PM = config("IGNORE_PM", default=True, cast=bool)
            self.LOG_GROUP = config("LOG_GROUP", default=0, cast=int)
            self.MAX_SAVED_MESSAGES = config(
                "MAX_SAVED_MESSAGES", default=300, cast=int
            )
            self.NO_GPU = config("NO_GPU", default=False, cast=bool)
            self.RSS_CHAT = config(
                "RSS_CHAT",
                default=str(),
            )
            self.RSS_DELAY = config("RSS_DELAY", default=60, cast=int)
            self.OWNER = config(
                "OWNER",
                default="",
            )
            self.TELEGRAPH_API = config(
                "TELEGRAPH_API", default="https://api.telegra.ph"
            )
        except Exception:
            print("Environment vars Missing; or")
            print("Something went wrong:")
            print(traceback.format_exc())
            exit()


class Runtime_Config:
    def __init__(self):
        self.initialized_client = False
        self.author = None
        self.author_url = None
        self.auto_save_msg_is_running = False
        self.block_nsfw = False
        self.client = None
        self.current_games_dict = {}
        self.disable_cic = False
        self.docker_deployed = False
        self.force_save_messages = False
        self.group_dict = {}
        self.games_dict = {}
        self.ignore_pm = False
        self.max_message_length = 4096
        self.me = None
        self.msg_leaderboard_counter = 0
        self.offline = False
        self.paused = False
        self.p_queue = []
        self.pending_saved_messages = []
        self.notes_dict = {}
        self.rss_dict = {}
        self.rss_ran_once = False
        self.user_dict = {}
        self.version = None


conf = Config()
bot = Runtime_Config()
