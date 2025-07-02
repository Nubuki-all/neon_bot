import asyncio

from sqlalchemy import Index, Integer, LargeBinary, String, and_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from bot import base_msg, msg_store_lock
from bot.config import bot, conf
from bot.utils.db_utils import save2db2
from bot.utils.log_utils import logger
from bot.utils.msg_utils import construct_event


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "Wa_Message"
    __table_args__ = (
        Index("idx_chat_id", "chat_id", "timestamp"),
        Index("idx_chat_w_id", "chat_id", "id", "timestamp"),
        Index("idx_chat_w_type", "chat_id", "timestamp", "type"),
        Index("idx_chat_w_revoke", "chat_id", "is_revoke", "timestamp"),
        Index("idx_chat_w_user", "chat_id", "timestamp", "user_id"),
        Index("idx_chat_w_visible_id", "chat_id", "id", "timestamp", "visible"),
    )
    _id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(30))
    id: Mapped[str] = mapped_column(String(30))
    is_revoke: Mapped[bool]
    raw: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    revoked_id: Mapped[str | None] = mapped_column(String(30))
    timestamp: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(30))
    user_id: Mapped[str] = mapped_column(String(30))
    visible: Mapped[bool]

    def __repr__(self) -> str:
        return (
            f"Message(_id={self._id!r}, "
            f"chat_id={self.chat_id!r}, "
            f"id={self.id!r}, "
            f"is_revoke={self.is_revoke!r}, "
            f"raw={self.raw!r}, "
            f"revoked_id={self.revoked_id!r}, "
            f"timestamp={self.timestamp!r}, "
            f"type={self.type!r}, "
            f"user_id={self.user_id!r}, "
            f"visible={self.visible!r})"
        )


engine = create_async_engine(
    conf.MSG_STORE,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    connect_args={"timeout": 10},
)
async_session = async_sessionmaker(engine, expire_on_commit=False)


def load_proto(data):
    msg = base_msg()
    msg.ParseFromString(data)
    return msg


async def save_messages(msgs):
    async with async_session() as session:
        items = [
            Message(
                chat_id=event.chat.id,
                id=event.id,
                is_revoke=event.is_revoke,
                raw=event.message.SerializeToString(),
                revoked_id=event.revoked_id,
                timestamp=event.timestamp,
                type=event.name,
                user_id=event.user.id,
                visible=True if ((event.media or event.text) and not event.protocol) else False,
            )
            for event in msgs
        ]
        async with session.begin():
            session.add_all(items)
        await session.commit()


async def get_messages(
    chat_ids: list | str, msg_ids: list | str = None, limit: int = None, visible=True
):
    try:
        chat_ids = [chat_ids] if isinstance(chat_ids, str) else [*chat_ids]
        if msg_ids:
            msg_ids = [msg_ids] if isinstance(msg_ids, str) else [*msg_ids]
        async with async_session() as session:
            stmt = (
                select(Message)
                .where(
                    and_(
                        Message.chat_id.in_(chat_ids),
                        Message.id.in_(msg_ids),
                        Message.visible == visible,
                    )
                )
                .order_by(Message.timestamp.desc())
                .limit(limit)
                if msg_ids
                else select(Message)
                .where(Message.chat_id.in_(chat_ids), Message.visible == visible)
                .order_by(Message.timestamp.desc())
                .limit(limit)
            )
            results = (await session.scalars(stmt)).all()
        return [construct_event(load_proto(msg_data.raw)) for msg_data in results]
    except Exception as e:
        raise e


async def get_messages_by_type(
    chat_ids: list | str, types: list | str, limit: int = None
):
    try:
        chat_ids = [chat_ids] if isinstance(chat_ids, str) else [*chat_ids]
        types = [types] if isinstance(types, str) else [*types]
        async with async_session() as session:
            stmt = (
                select(Message)
                .where(and_(Message.chat_id.in_(chat_ids), Message.type.in_(types)))
                .order_by(Message.timestamp.desc())
                .limit(limit)
            )
            results = (await session.scalars(stmt)).all()
        return [construct_event(load_proto(msg_data.raw)) for msg_data in results]
    except Exception as e:
        raise e


async def get_deleted_message_ids(chat_ids, limit=None, user_ids=None):
    try:
        chat_ids = [chat_ids] if isinstance(chat_ids, str) else [*chat_ids]
        if user_ids:
            user_ids = [user_ids] if isinstance(user_ids, str) else [*user_ids]
        async with async_session() as session:
            stmt = (
                select(Message)
                .where(
                    and_(
                        Message.chat_id.in_(chat_ids),
                        Message.user_id.in_(user_ids),
                        Message.is_revoke,
                    )
                )
                .order_by(Message.timestamp.desc())
                .limit(limit)
                if user_ids
                else select(Message)
                .where(Message.chat_id.in_(chat_ids), Message.is_revoke)
                .order_by(Message.timestamp.desc())
                .limit(limit)
            )
            results = (await session.scalars(stmt)).all()
        return [msg_data.revoked_id for msg_data in results]
    except Exception as e:
        raise e


async def auto_save_msg():
    bot.auto_save_msg_is_running = True
    while True:
        if messages := bot.pending_saved_messages:
            async with msg_store_lock:
                try:
                    while len(messages) < 2 and not bot.force_save_messages:
                        await asyncio.sleep(1)
                    await save_messages(messages)
                    if bot.msg_leaderboard_counter > 10:
                        await save2db2(bot.group_dict, "groups")
                        bot.msg_leaderboard_counter = 0
                except Exception:
                    await logger(Exception)
                finally:
                    messages.clear()
                    if bot.force_save_messages:
                        bot.force_save_messages = False
            await asyncio.sleep(1)
        await asyncio.sleep(3)
