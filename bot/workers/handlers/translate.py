import re
from functools import cache

import aiohttp

from bot.config import bot
from bot.utils.bot_utils import sync_to_async
from bot.utils.db_utils import save2db2
from bot.utils.log_utils import log, logger
from bot.utils.msg_utils import (
    chat_is_allowed,
    function_dict,
    user_is_admin,
    user_is_allowed,
    user_is_privileged,
)

# Languages py3langid can detect, from ISO 639
LANGUAGES = {
    "ace": "Achinese", "af": "Afrikaans", "am": "Amharic", "an": "Aragonese",
    "ar": "Arabic", "ary": "Moroccan Arabic", "arz": "Egyptian Arabic", "as": "Assamese",
    "az": "Azerbaijani", "ba": "Bashkir", "bcl": "Central Bikol", "be": "Belarusian",
    "bg": "Bulgarian", "bn": "Bangla", "br": "Breton", "bs": "Bosnian", "ca": "Catalan",
    "crh": "Crimean Tatar", "cs": "Czech", "cy": "Welsh", "da": "Danish", "de": "German",
    "dz": "Dzongkha", "el": "Greek", "en": "English", "eo": "Esperanto", "es": "Spanish",
    "et": "Estonian", "eu": "Basque", "ext": "Extremaduran", "fa": "Persian",
    "fi": "Finnish", "fo": "Faroese", "fr": "French", "fuv": "Nigerian Fulfulde",
    "fy": "Western Frisian", "ga": "Irish", "gcf": "Guadeloupean Creole",
    "gcr": "Guianese Creole", "gd": "Scottish Gaelic", "gl": "Galician",
    "gom": "Goan Konkani", "grc": "Ancient Greek", "gu": "Gujarati", "gug": "Guarani",
    "guw": "Gun", "ha": "Hausa", "hbo": "Ancient Hebrew", "he": "Hebrew", "hi": "Hindi",
    "hr": "Croatian", "ht": "Haitian Creole", "hu": "Hungarian", "hy": "Armenian",
    "id": "Indonesian", "ig": "Igbo", "is": "Icelandic", "it": "Italian", "ja": "Japanese",
    "jv": "Javanese", "ka": "Georgian", "kab": "Kabyle", "kik": "Kikuyu", "kk": "Kazakh",
    "km": "Khmer", "kn": "Kannada", "ko": "Korean", "ku": "Kurdish", "ky": "Kyrgyz",
    "la": "Latin", "lb": "Luxembourgish", "lg": "Ganda", "lij": "Ligurian",
    "ln": "Lingala", "lo": "Lao", "lt": "Lithuanian", "ltg": "Latgalian", "lv": "Latvian",
    "mg": "Malagasy", "mk": "Macedonian", "ml": "Malayalam", "mn": "Mongolian",
    "mr": "Marathi", "ms": "Malay", "mt": "Maltese", "my": "Burmese", "ne": "Nepali",
    "nl": "Dutch", "nn": "Norwegian Nynorsk", "no": "Norwegian", "nso": "Pedi",
    "oc": "Occitan", "om": "Oromo", "or": "Odia", "pa": "Punjabi", "pcm": "Nigerian Pidgin",
    "pl": "Polish", "ps": "Pashto", "pt": "Portuguese", "qu": "Quechua", "ro": "Romanian",
    "ru": "Russian", "rw": "Kinyarwanda", "sa": "Sanskrit", "sdh": "Southern Kurdish",
    "se": "Northern Sami", "si": "Sinhala", "sk": "Slovak", "sl": "Slovenian",
    "sn": "Shona", "so": "Somali", "sq": "Albanian", "sr": "Serbian",
    "st": "Southern Sotho", "sv": "Swedish", "sw": "Swahili", "ta": "Tamil",
    "te": "Telugu", "tg": "Tajik", "th": "Thai", "tk": "Turkmen", "tl": "Tagalog",
    "tr": "Turkish", "tt": "Tatar", "ug": "Uyghur", "uk": "Ukrainian", "ur": "Urdu",
    "uz": "Uzbek", "uzs": "Southern Uzbek", "vec": "Venetian", "vi": "Vietnamese",
    "vo": "Volapük", "wa": "Walloon", "wuu": "Wu Chinese", "xh": "Xhosa", "yo": "Yoruba",
    "yue": "Cantonese", "zh": "Chinese", "zu": "Zulu",
}  # fmt: skip
# Variants that count as their main language, so they aren't translated into it
FAMILY = {
    "ary": "ar",
    "arz": "ar",
    "hbo": "he",
    "grc": "el",
    "nn": "no",
    "sdh": "ku",
    "uzs": "uz",
    "wuu": "zh",
    "yue": "zh",
}
# Languages that can be translated into, with Google's code where it differs
TARGETS = {
    code: {"he": "iw", "jv": "jw", "zh": "zh-CN"}.get(code, code)
    for code in (
        "af am ar az be bg bn bs ca cs cy da de el en eo es et eu fa fi fr fy ga gd gl "
        "gu ha he hi hr ht hu hy id ig is it ja jv ka kk km kn ko ku ky la lb lg lo lt "
        "lv mg mk ml mn mr ms mt my ne nl no or pa pl ps pt qu ro ru rw sa si sk sl sn so "
        "sq sr st sv sw ta te tg th tk tl tr tt ug uk ur uz vi xh yo zh zu"
    ).split()
}

# Short or ambiguous messages ("ok", "lol") are left alone
MIN_LETTERS = 12
MIN_CONFIDENCE = 0.8
MAX_CHARS = 5000
GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"

_noise = re.compile(r"https?://\S+|www\.\S+|@\d+|```.*?```|[*_~`>]", re.S)
_mention = re.compile(r"@(\d{5,16})")


@cache
def identifier():
    from py3langid.langid import MODEL_FILE, LanguageIdentifier

    return LanguageIdentifier.from_model_file(MODEL_FILE, norm_probs=True)


def lang_code(name: str) -> str | None:
    """A language code from a code or an English name"""
    name = name.strip().casefold()
    if name in LANGUAGES:
        return name
    return next((c for c, n in LANGUAGES.items() if n.casefold() == name), None)


def family(code: str) -> str:
    return FAMILY.get(code, code)


async def detect(text: str) -> str | None:
    """The message's language, or None when it's too short or unclear"""
    text = _noise.sub(" ", text)
    if sum(c.isalpha() for c in text) < MIN_LETTERS:
        return None
    lang, prob = await sync_to_async(identifier().classify, text)
    if prob < MIN_CONFIDENCE or lang not in LANGUAGES:
        return None
    return lang


async def translate(text: str, target: str) -> str:
    params = {"client": "gtx", "sl": "auto", "tl": TARGETS[target], "dt": "t"}
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(GOOGLE_URL, params=params, data={"q": text}) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    return "".join(part[0] for part in data[0] if part and part[0])


def same_text(a: str, b: str) -> bool:
    return " ".join(a.casefold().split()) == " ".join(b.casefold().split())


async def auto_translate(event, _, client):
    """
    Automatic handler (not a command): replies with a translation when a message
    isn't in the chat's language (see autotranslate).
    """
    try:
        if event.outgoing or event.is_edit:
            return
        settings = bot.group_dict.get(event.chat.id, {}).get("auto_translate")
        if not settings:
            return
        text = event.text or event.caption
        if not text or len(text) > MAX_CHARS:
            return
        if text.split()[0] in function_dict:
            return
        user = event.from_user.id
        if not user_is_privileged(user):
            if not (chat_is_allowed(event) and user_is_allowed(user)):
                return
        target = settings["lang"]
        lang = await detect(text)
        if not lang or family(lang) == target:
            return
        if family(lang) in settings.get("ignore", []):
            return
        try:
            translated = await translate(text, target)
        except Exception:
            # Not worth a log chat message for every message
            return log(Exception, warning=True)
        # Unchanged text means Google saw it as the target language already
        if not translated or same_text(translated, text):
            return
        # Keep @mentions from pinging people again
        translated = _mention.sub("@⁠\\1", translated)
        await event.reply(f"🌐 _Translated from {LANGUAGES[lang]}:_\n{translated}")
    except Exception:
        await logger(Exception)


async def autotranslate(event, args, client):
    """
    Translates messages that aren't in the chat's language.
    In groups only the owner, sudoers and admins can change it. In PM, anyone the
    bot answers there can (with IGNORE_PM on, only the owner and sudoers).
    With no arguments, shows the current setting.

    Usage:
        autotranslate <language> [-i <language> ...] - Translate into the language
        autotranslate off - Stop translating
    Arguments:
        language: a code or English name, e.g. en or english
        -i <language> ... : [Optional] languages to leave untranslated (e.g. pcm for
            Nigerian Pidgin); -i none clears the list. Left out, the list is kept.
    Messages shorter than about two words, or whose language is unclear, aren't translated.
    """
    user = event.from_user.id
    if not user_is_privileged(user):
        if not chat_is_allowed(event):
            return
        if not user_is_allowed(user):
            return await event.react("⛔")
    try:
        gc_dict = bot.group_dict.setdefault(event.chat.id, {})
        settings = gc_dict.get("auto_translate")
        if not args:
            if not settings:
                return await event.reply("*Auto translation is off in this chat.*")
            ignore = ", ".join(LANGUAGES[c] for c in settings.get("ignore", []))
            return await event.reply(
                f"*Translating into {LANGUAGES[settings['lang']]}.*"
                + (f"\n*Left untranslated:* {ignore}" if ignore else "")
            )
        if event.chat.is_group and not user_is_privileged(user):
            group_info = await client.get_group_info(event.chat.jid)
            if not user_is_admin(user, group_info.Participants):
                return await event.react("🚫")
        if args.strip().casefold() == "off":
            gc_dict.pop("auto_translate", None)
            await save2db2(bot.group_dict, "groups")
            return await event.reply("*Auto translation is now off.*")
        words = args.split()
        ignore_words = None
        if "-i" in words:
            at = words.index("-i")
            words, ignore_words = words[:at], words[at + 1 :]
        target = lang_code(" ".join(words))
        if target not in TARGETS:
            return await event.reply(
                f"*Can't translate into:* {' '.join(words) or '?'}\n"
                f"Use a language code or English name, e.g. en, english, fr, yoruba."
            )
        ignore = (settings or {}).get("ignore", [])
        if ignore_words is not None:
            names = [w for w in re.split(r"[,\s]+", " ".join(ignore_words)) if w]
            if [n.casefold() for n in names] == ["none"]:
                ignore = []
            else:
                codes = [lang_code(n) for n in names]
                if None in codes or not codes:
                    unknown = [n for n, c in zip(names, codes) if not c] or ["?"]
                    return await event.reply(
                        f"*Unknown language(s):* {', '.join(unknown)}\n"
                        "Use codes for names with spaces, e.g. pcm for Nigerian Pidgin."
                    )
                ignore = list(dict.fromkeys(family(c) for c in codes))
        gc_dict["auto_translate"] = {"lang": target, "ignore": ignore}
        await save2db2(bot.group_dict, "groups")
        skipped = ", ".join(LANGUAGES[c] for c in ignore)
        await event.reply(
            f"*Messages in other languages will be translated into {LANGUAGES[target]}.*"
            + (f"\n*Left untranslated:* {skipped}" if skipped else "")
        )
    except Exception:
        await logger(Exception)
        await event.react("❌")
