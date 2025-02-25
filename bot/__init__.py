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


import asyncio
import logging
import os
import re
import shlex
import subprocess
import sys
import time
import traceback
from logging import DEBUG, INFO, basicConfig, getLogger, warning
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse

from html_telegraph_poster import TelegraphPoster
from html_telegraph_poster import errors as telegraph_errors
from neonize.aioze.client import NewAClient
from neonize.events import (
    CallOfferEv,
    ConnectedEv,
    DisconnectedEv,
    GroupInfoEv,
    JoinedGroupEv,
    LoggedOutEv,
    MessageEv,
    PairStatusEv,
    ReceiptEv,
    event,
)
from neonize.proto.Neonize_pb2 import Message as base_msg
from neonize.proto.Neonize_pb2 import MessageInfo as base_msg_info
from neonize.proto.Neonize_pb2 import MessageSource as base_msg_source
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (
    AudioMessage,
    ContactMessage,
    ContextInfo,
    DocumentMessage,
    ExtendedTextMessage,
    ImageMessage,
    Message,
    StickerMessage,
    VideoMessage,
)
from neonize.utils import jid, log

from .config import bot, conf

heavy_proc_lock = asyncio.Lock()
local_gcdb = ".local_groups.pkl"
local_rdb = ".local_rssdb.pkl"
local_udb = ".local_users.pkl"
local_ndb = ".local_notedb.pkl"
log_file_name = "logs.txt"
msg_store_file = "Msg_store"
msg_store_lock = asyncio.Lock()
rss_dict_lock = asyncio.Lock()
sudo_btn_lock = asyncio.Lock()
uptime = time.time()
version_file = "version.txt"
wa_db = "db.sqlite3"
con_ind = ".CONNECTED"

if os.path.exists(log_file_name):
    with open(log_file_name, "r+") as f_d:
        f_d.truncate(0)

logging.basicConfig(
    level=logging.INFO,
    force=True,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(log_file_name, maxBytes=2097152000, backupCount=10),
        logging.StreamHandler(),
    ],
)
logging.getLogger("neonize").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)

LOGS = logging.getLogger(__name__)

no_verbose = [
    "apscheduler.executors.default",
    "httpx",
]
if not conf.DEBUG:
    log.setLevel(logging.INFO)
    for item in no_verbose:
        logging.getLogger(item).setLevel(logging.WARNING)

bot.repo_branch = (
    subprocess.check_output(["git rev-parse --abbrev-ref HEAD"], shell=True)
    .decode()
    .strip()
    if os.path.exists(".git")
    else None
)
if os.path.exists(version_file):
    with open(version_file, "r") as file:
        bot.version = file.read().strip()

if sys.version_info < (3, 10):
    LOGS.critical("Please use Python 3.10+")
    exit(1)

LOGS.info("Starting...")

bot.ignore_pm = conf.IGNORE_PM
bot.block_nsfw = conf.BLOCK_NSFW
bot.disable_cic = conf.DISABLE_CIP
bot.tgp_client = TelegraphPoster(use_api=True, telegraph_api_url=conf.TELEGRAPH_API)

bot.client = NewAClient(wa_db)
