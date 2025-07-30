import json
from abc import ABC, abstractmethod

from google.protobuf.json_format import MessageToDict
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (
    AudioMessage,
    DocumentMessage,
    ExtendedTextMessage,
    ImageMessage,
    PollUpdateMessage,
    ProtocolMessage,
    ReactionMessage,
    SenderKeyDistributionMessage,
    StickerMessage,
    StickerPackMessage,
    VideoMessage,
)
from neonize.types import MessageWithContextInfo

from bot import JID, NewAClient, base_msg_info, base_msg_source

# --- Base Interfaces with default __init__ ---


class BaseUser(ABC):
    def __init__(self):
        self.name: str = ""
        self.jid: JID | None = None
        self.id: str = ""
        self.server: str = ""
        self.is_empty: bool = False
        self.is_hidden: bool = False

    @abstractmethod
    def construct(self, info: base_msg_info, alt: bool = False):
        """Populate user fields from a Message.Info"""
        ...


class BaseChat(ABC):
    def __init__(self):
        self.name: str = ""
        self.jid: JID | None = None
        self.id: str = ""
        self.server: str = ""
        self.is_group: bool = False
        self.is_empty: bool = False

    @abstractmethod
    def construct(self, msg_source: base_msg_source):
        """Populate chat fields from a MessageSource"""
        ...


class BaseEvent(ABC):
    def __init__(self):
        # Core messaging attributes
        self.client: NewAClient | None = None
        self.constructed: bool = False
        self.id: str | None = None
        self.type: str | None = None
        self.media_type: str | None = None
        self.text: str | None = None
        self.caption: str | None = None
        self.timestamp: int | None = None
        self.is_actual_media: bool = False
        self.is_view_once: bool = False
        self.is_album: bool = False
        self.constructed: bool = False
        self.is_edit: bool = False
        self.is_revoke: bool = False
        self.album_id: str | None = None
        self.edited_id: str | None = None
        self.lid_address: bool = False
        self.revoked_id: str | None = None

        # Sub-objects
        self.chat: BaseChat | None = None
        self.user: BaseUser | None = None
        self.alt_user: BaseUser | None = None
        self.from_user: BaseUser | None = None

        # Populated media/message-related attributes
        self.audio: AudioMessage | None = None
        self.document: DocumentMessage | None = None
        self.extendedText: ExtendedTextMessage | None = None
        self.image: ImageMessage | None = None
        self.media: MessageWithContextInfo | None = None
        self.protocol: ProtocolMessage | None = None
        self.ptv: VideoMessage | None = None
        self.reaction: ReactionMessage | None = None
        self.video: VideoMessage | None = None
        self.view_once = None
        self.sticker: StickerMessage | None = None
        self.stickerPack: StickerPackMessage | None = None
        self.message_association = None
        self.pollUpdate: PollUpdateMessage | None = None
        self.senderKeyDistribution: SenderKeyDistributionMessage | None = None

        # Finally the Neonize Message Event
        self.message: MessageEv | None = None

    def __str__(self):
        def serialize(obj):
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            elif hasattr(obj, "__dict__"):
                # Redact .jid if present
                d = obj.__dict__.copy()
                if "jid" in d and d["jid"]:
                    d["jid"] = "…"
                if "lid" in d and d["lid"]:
                    d["lid"] = "…"
                return {k: serialize(v) for k, v in d.items()}
            elif isinstance(obj, (list, tuple)):
                return [serialize(v) for v in obj]
            elif isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            return str(obj)

        def default(obj):
            keys_to_pop = ("Info", "Raw")
            message = MessageToDict(obj)
            for key in keys_to_pop:
                if key in message:
                    message.pop(key)
            return message

        exclude = (
            "_",
            "client",
            "constructed",
            "message_association",
        )
        skip_serialize = {"message"}
        to_bool = {
            "media",
            "audio",
            "document",
            "extendedText",
            "image",
            "media",
            "protocol",
            "ptv",
            "reaction",
            "video",
            "view_once",
            "sticker",
            "stickerPack",
            "reply_to_message",
            "pollUpdate",
            "senderKeyDistribution",
        }
        result = {}
        for k, v in self.__dict__.items():
            if k in skip_serialize:
                result[k] = v
                continue
            elif k.startswith(exclude):
                continue
            result[k] = (
                bool(v) if k in to_bool else serialize(v)
            )  # Knowing whether they exist or not is enough

        return json.dumps(result, default=default, indent=4, ensure_ascii=False)

    @abstractmethod
    def construct(self, message, add_replied: bool = True):
        """Initialize event from a MessageEv object."""
        ...


class Chat(BaseChat):
    def __init__(self):
        super().__init__()

    def construct(self, msg_source: base_msg_source):
        self.jid = msg_source.Chat
        self.id = self.jid.User
        self.is_empty = msg_source.Chat.IsEmpty
        self.is_group = msg_source.IsGroup
        self.server = self.jid.Server


class User(BaseUser):
    def __init__(self):
        super().__init__()

    def construct(self, info: base_msg_info, alt: bool = False):
        self.name = info.Pushname
        self.jid = (
            info.MessageSource.Sender if not alt else info.MessageSource.SenderAlt
        )
        if self.jid == JID():
            self.jid = None
            return
        self.id = self.jid.User
        self.is_empty = self.jid.IsEmpty
        self.server = self.jid.Server
        self.is_hidden = self.server == "lid"
