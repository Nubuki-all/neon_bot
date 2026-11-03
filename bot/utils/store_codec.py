"""
Turns the bot's stored dicts into plain JSON/BSON-safe data and back.

Plain values (str, int, float, bool, None, lists, dicts with ordinary
string keys) are kept as they are. Everything else becomes a dict tagged
with "__type__", so it reads back as the same Python value:
    set, tuple, datetime, bytes (base64),
    dicts with keys that aren't plain strings (ints, or strings with "."
    or a leading "$", which MongoDB can't hold) as a list of pairs,
    protobuf messages (serialized, base64, with their type name),
    the classes notes and filters store as their type (str, bytes, Message).
"""

import base64
import datetime

from google.protobuf import descriptor_pool, message_factory
from google.protobuf.message import Message as ProtoMessage
from neonize.proto import Neonize_pb2
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import Message

# Not "$type": MongoDB before 5.0 refuses field names starting with "$"
TAG = "__type__"
# Classes stored as values (note_type, filter_type) and their names
CLASSES = {"str": str, "bytes": bytes, "Message": Message}
# Imported so their message types are registered before anything loads
PROTO_MODULES = (Neonize_pb2, Message)


def _plain_key(key) -> bool:
    return (
        isinstance(key, str)
        and not key.startswith("$")
        and "." not in key
        and key != TAG
    )


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def encode(value, path="value"):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [encode(v, f"{path}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, dict):
        if all(_plain_key(k) for k in value):
            return {k: encode(v, f"{path}.{k}") for k, v in value.items()}
        return {
            TAG: "map",
            "items": [
                [encode(k, f"{path} key"), encode(v, f"{path}[{k!r}]")]
                for k, v in value.items()
            ],
        }
    if isinstance(value, (set, frozenset)):
        items = [encode(v, f"{path} item") for v in value]
        return {TAG: "set", "items": sorted(items, key=repr)}
    if isinstance(value, tuple):
        return {TAG: "tuple", "items": [encode(v, path) for v in value]}
    if isinstance(value, datetime.datetime):
        return {TAG: "datetime", "value": value.isoformat()}
    if isinstance(value, (bytes, bytearray)):
        return {TAG: "bytes", "value": _b64(bytes(value))}
    if isinstance(value, type):
        name = next((n for n, c in CLASSES.items() if c is value), None)
        if name:
            return {TAG: "class", "value": name}
    elif isinstance(value, ProtoMessage):
        # Parsing a protobuf can't run code, unlike unpickling
        return {
            TAG: "proto",
            "class": value.DESCRIPTOR.full_name,
            "value": _b64(value.SerializeToString()),
        }
    raise TypeError(f"Can't store {type(value).__name__} at {path}")


def _proto_class(full_name: str):
    descriptor = descriptor_pool.Default().FindMessageTypeByName(full_name)
    return message_factory.GetMessageClass(descriptor)


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    kind = value.get(TAG)
    if kind is None:
        return {k: decode(v) for k, v in value.items()}
    if kind == "map":
        return {decode(k): decode(v) for k, v in value["items"]}
    if kind == "set":
        return {decode(v) for v in value["items"]}
    if kind == "tuple":
        return tuple(decode(v) for v in value["items"])
    if kind == "datetime":
        return datetime.datetime.fromisoformat(value["value"])
    if kind == "bytes":
        return base64.b64decode(value["value"])
    if kind == "class":
        return CLASSES[value["value"]]
    if kind == "proto":
        return _proto_class(value["class"]).FromString(base64.b64decode(value["value"]))
    raise ValueError(f"Unknown stored type {kind!r}")
