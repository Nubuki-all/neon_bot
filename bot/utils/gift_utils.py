import asyncio
import re
from datetime import datetime, timedelta
from urllib.parse import quote

import aiohttp
from apscheduler.triggers.interval import IntervalTrigger

from bot.config import bot, conf
from bot.workers.auto.schedule import scheduler2

from .db_utils import save2db2
from .log_utils import log
from .msg_utils import send_rss

# Tried in order; later ones are fallbacks for when the first is down
CODE_FEEDS = (
    "https://hoyo-codes.seria.moe/codes?game=genshin",
    "https://api.ennead.cc/mihoyo/genshin/codes",
)
GIFT_CHECK_INTERVAL = 30 * 60
# Codes go into links, so entries that don't look like a code are dropped
_valid_code = re.compile(r"[A-Za-z0-9]{4,64}")
# "Mora*10000" (seria.moe) or "Mora ×10000" (ennead.cc)
_reward_amount = re.compile(r"\s*[*×x]\s*(\d+)\s*$")


def parse_rewards(rewards) -> list[str]:
    """
    Rewards as ["Mora ×10,000", ...] from either feed: a ";"-separated
    string with "*" before the amount, or a list using "×".
    """
    if isinstance(rewards, str):
        rewards = rewards.split(";")
    if not isinstance(rewards, list):
        return []
    parsed = []
    for reward in map(str, rewards):
        reward = reward.strip()
        if not reward:
            continue
        match = _reward_amount.search(reward)
        if match:
            name = reward[: match.start()].strip()
            reward = f"{name} ×{int(match.group(1)):,}"
        parsed.append(reward)
    return parsed


def parse_codes(data: dict) -> list[dict]:
    """
    Active codes as [{"code", "rewards": [str]}] from either feed's format;
    expired, other games' and malformed entries are dropped.
    """
    if not isinstance(data, dict) or data.get("game", "genshin") != "genshin":
        raise ValueError("Unexpected code feed format")
    entries = data.get("codes", data.get("active"))
    if not isinstance(entries, list):
        raise ValueError("Unexpected code feed format")
    codes = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("status", "OK")).casefold() not in ("ok", "active"):
            continue
        if entry.get("game", "genshin") != "genshin":
            continue
        code = str(entry.get("code") or "").strip()
        if not _valid_code.fullmatch(code):
            continue
        rewards = parse_rewards(entry.get("rewards"))
        codes.setdefault(code.casefold(), {"code": code, "rewards": rewards})
    return list(codes.values())


async def fetch_codes() -> list[dict]:
    """The current codes from the first feed that answers"""
    errors = []
    timeout = aiohttp.ClientTimeout(total=20)
    for url in CODE_FEEDS:
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    return parse_codes(await resp.json(content_type=None))
        except Exception as e:
            errors.append(f"{url}: {e}")
    raise RuntimeError("Couldn't fetch Genshin codes: " + "; ".join(errors))


def get_msg_from_codes(codes: list, auto: bool = False):
    msg = "*Genshin Impact Redeem Codes*\n\n"
    for no, code in enumerate(codes, start=1):
        link = f"https://genshin.hoyoverse.com/en/gift?code={
            quote(
                code['code'],
                safe='')}"
        rewards = "\n".join(f"• {r}" for r in code["rewards"]) or "• Unknown"
        msg += f"*{no}.* {link}\n{rewards}"
        msg += "\n\n"
    msg += "_I'm a bot and this action was performed automatically._" if auto else ""
    return msg.strip()


async def gift_code_monitor():
    try:
        if not bot.gift_dict["chats"]:
            return
        new_codes = [
            code
            for code in await fetch_codes()
            if code["code"] not in bot.gift_dict["codes"]
        ]
        if not new_codes:
            return
        msg = get_msg_from_codes(new_codes, auto=True)
        expanded_chat = []
        for chat in bot.gift_dict["chats"]:
            (
                expanded_chat.append(chat)
                if chat
                else expanded_chat.extend(conf.RSS_CHAT.split())
            )
        for chat in expanded_chat:
            chat, _, server = chat.partition(":")
            try:
                await send_rss(msg, chat, [], server or "s.whatsapp.net")
                await asyncio.sleep(5)
            except Exception:
                log(Exception)
        bot.gift_dict["codes"].extend(code["code"] for code in new_codes)
        await save2db2(bot.gift_dict, "gift")
        log(e="Found and sent new codes to chat!")
    except Exception:
        log(Exception)


# On scheduler2: the rss scheduler pauses itself when no feeds are active
scheduler2.add_job(
    gift_code_monitor,
    trigger=IntervalTrigger(seconds=GIFT_CHECK_INTERVAL),
    id="gift_monitor",
    misfire_grace_time=15,
    max_instances=1,
    next_run_time=datetime.now() + timedelta(seconds=60),
    replace_existing=True,
)
