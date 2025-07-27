from chatterbot import ChatBot
from chatterbot.trainers import ChatterBotCorpusTrainer

from bot.config import conf

from .bot_utils import ensure_default_db

if conf.CB_DB:
    chat_bot = ChatBot(
        "N.",
        storage_adapter="chatterbot.storage.MongoDatabaseAdapter",
        logic_adapters=[
            "chatterbot.logic.BestMatch",
            "chatterbot.logic.MathematicalEvaluation",
            "chatterbot.logic.TimeLogicAdapter",
        ],
        database_uri=ensure_default_db(conf.CB_DB, "chatterbot"),
    )
    trainer = ChatterBotCorpusTrainer(chat_bot)
    trainer.train("chatterbot.corpus.english")
else:
    chat_bot = None
