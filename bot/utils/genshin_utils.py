import asyncio
import json
import logging
import random
import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

LOG = logging.getLogger(__name__)
CODE_FEEDS = (
    "https://hoyo-codes.seria.moe/codes?game=genshin",
    "https://api.ennead.cc/mihoyo/genshin/codes",
)


def parse_codes(payload):
    if isinstance(payload, dict):
        if payload.get("game", "genshin") != "genshin":
            raise ValueError("The feed returned codes for a different game.")
        payload = payload.get("codes", payload.get("active"))
    if not isinstance(payload, list):
        raise ValueError("The code feed returned an unexpected format.")
    codes = {}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("status", "OK")).casefold() not in {"ok", "active"}:
            continue
        if entry.get("game", "genshin") != "genshin":
            continue
        code = entry.get("code")
        if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9]{4,64}", code.strip()):
            code = code.strip()
            codes.setdefault(code.casefold(), code)
    return list(codes.values())


def fetch_codes():
    errors = []
    for url in CODE_FEEDS:
        try:
            request = Request(url, headers={"User-Agent": "NeonBot-GenshinCodes/1.0"})
            with urlopen(request, timeout=15) as response:
                body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ValueError("The code feed is too large.")
            return parse_codes(json.loads(body))
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    raise RuntimeError("Could not fetch Genshin codes: " + "; ".join(errors))


def format_code(code):
    return (
        f"[GI] - new code\n{code}\n"
        f"https://genshin.hoyoverse.com/en/gift?code={quote(code, safe='')}"
    )


def next_check_seconds():
    return random.randint(15 * 60, 60 * 60)


class CodeStore:
    def __init__(self, path):
        self.path = Path(path)
        self.chats = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or any(
                not isinstance(codes, list)
                or not all(isinstance(code, str) for code in codes)
                for codes in data.values()
            ):
                raise ValueError(
                    "The Genshin code history is damaged; refusing to reset it."
                )
            self.chats = {
                chat: {code.casefold() for code in codes}
                for chat, codes in data.items()
            }

    def subscribe(self, chat, codes):
        if chat not in self.chats:
            self.chats[chat] = {code.casefold() for code in codes}
            self._save()

    def unsubscribe(self, chat):
        if chat in self.chats:
            del self.chats[chat]
            self._save()

    def pending(self, chat, codes):
        if chat not in self.chats:
            return []
        return [code for code in codes if code.casefold() not in self.chats[chat]]

    def delivered(self, chat, code):
        if chat in self.chats:
            self.chats[chat].add(code.casefold())
            self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {chat: sorted(codes) for chat, codes in self.chats.items()}, indent=2
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)


class GenshinWatcher:
    def __init__(self, path):
        self.path = Path(path)
        self._store = None
        self._task = None
        self.lock = asyncio.Lock()

    @property
    def store(self):
        if self._store is None:
            self._store = CodeStore(self.path)
        return self._store

    def start(self, send, is_allowed):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._run(send, is_allowed), name="genshin-codes"
            )

    async def stop(self):
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self, send, is_allowed):
        while True:
            try:
                await self.check(send, is_allowed)
            except Exception:
                LOG.exception("Genshin code check failed; retrying on the next check")
            await asyncio.sleep(next_check_seconds())

    async def check(self, send, is_allowed):
        chats = [chat for chat in self.store.chats if is_allowed(chat)]
        if not chats:
            return
        codes = await asyncio.to_thread(fetch_codes)
        for chat in chats:
            for code in self.store.pending(chat, codes):
                async with self.lock:
                    if chat not in self.store.chats or not is_allowed(chat):
                        break
                    try:
                        await send(chat, format_code(code))
                    except Exception:
                        LOG.exception(
                            "Could not post Genshin code to %s; will retry", chat
                        )
                        break
                    self.store.delivered(chat, code)
