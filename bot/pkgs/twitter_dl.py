import asyncio
import json
import logging
import os
import re
import subprocess
import urllib.parse
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from http.cookiejar import Cookie, CookieJar
from typing import Any

import aiofiles
import httpx

_log_ = logging.getLogger(__name__)

# ---------- Constants ----------
API_HOSTNAME = "x.com"
API_BASE = f"https://{API_HOSTNAME}/i/api/graphql/"
API_ENDPOINT = API_BASE + "2ICDjqPd81tulZcYrtpTuQ/TweetResultByRestId"
AUTH_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

TWEET_URL_RE = re.compile(
    r"https?://(?:fx|vx|fixup)?(?:twitter|x)\.com/([^/]+)/status/(?P<id>\d+)"
)
SHORT_URL_RE = re.compile(r"https?://t\.co/(?P<id>\w+)")
RESOLUTION_RE = re.compile(r"(\d+)x(\d+)")

# ---------- Data classes ----------


@dataclass
class DownloadResult:
    """Result of a downloaded media item."""

    local_path: str
    caption: str
    media_type: str  # "image" or "video"
    source_url: str
    thumbnail_url: str
    width: int | None = None
    height: int | None = None


@dataclass
class MediaFormat:
    """Represents a single media format (video variant or image)."""

    url: str
    bitrate: int | None = None
    width: int = 0
    height: int = 0
    duration: int | None = None  # seconds


@dataclass
class MediaItem:
    """Represents a single media entity (image or video)."""

    type: str  # "image" or "video"
    thumbnail: str | None = None
    formats: list[MediaFormat] = field(default_factory=list)  # for video
    url: str | None = None  # for image
    duration: int | None = None  # seconds


@dataclass
class TweetInfo:
    """Extracted tweet data."""

    caption: str
    media: list[MediaItem]


def is_valid_twitter_url(url: str) -> bool:
    """Check if the URL is a valid Twitter/X post or short link."""
    return bool(TWEET_URL_RE.search(url) or SHORT_URL_RE.search(url))


# ---------- Cookie helpers ----------


def load_netscape_cookies(filepath: str) -> CookieJar:
    """Load Netscape-format cookies into a CookieJar."""
    jar = CookieJar()
    with open(filepath, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 7:
                continue
            raw_domain, _flag, path, secure, expires, name, value = parts
            domain = raw_domain.lstrip(".")
            secure_flag = secure.lower() == "true"
            expires_ts = int(expires) if expires and expires != "0" else None
            cookie = Cookie(
                version=0,
                name=name,
                value=value,
                port=None,
                port_specified=False,
                domain=domain,
                domain_specified=True,
                domain_initial_dot=raw_domain.startswith("."),
                path=path or "/",
                path_specified=True,
                secure=secure_flag,
                expires=expires_ts,
                discard=expires_ts is None,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
            jar.set_cookie(cookie)
    return jar


def cookies_to_dict(jar: CookieJar) -> dict[str, str]:
    """Convert CookieJar to a dict for httpx."""
    return {c.name: c.value for c in jar}


# ---------- API helpers ----------
def build_api_headers(csrf_token: str) -> dict[str, str]:
    """Build required headers for Twitter GraphQL API."""
    return {
        "authorization": f"Bearer {AUTH_TOKEN}",
        "x-twitter-auth-type": "OAuth2Client",
        "x-twitter-client-language": "en",
        "x-twitter-active-user": "yes",
        "x-csrf-token": csrf_token,
    }


def build_api_query(tweet_id: str) -> str:
    """Build query string for the GraphQL request."""
    variables = {
        "tweetId": tweet_id,
        "withCommunity": False,
        "includePromotedContent": False,
        "withVoice": False,
    }
    features = {
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": False,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "responsive_web_media_download_video_enabled": False,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
    }
    field_toggles = {"withArticleRichContentState": False}

    params = {
        "variables": json.dumps(variables, separators=(",", ":")),
        "features": json.dumps(features, separators=(",", ":")),
        "fieldToggles": json.dumps(field_toggles, separators=(",", ":")),
    }
    return urllib.parse.urlencode(params)


def parse_resolution_from_url(url: str) -> tuple[int, int]:
    """Extract width and height from a video URL."""
    match = RESOLUTION_RE.search(url)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def sanitize_caption(text: str) -> str:
    """Remove t.co links from caption text."""
    if not text:
        return ""
    return re.sub(r"https?://t\.co/\S+", "", text).strip()


# ---------- Vork muxer detection and remux ----------
def is_vork_muxer(file_path: str) -> bool:
    """Detect if an MP4 file was muxed with Twitter's vork muxer."""
    import struct

    try:
        with open(file_path, "rb") as f:
            data = f.read(4096 * 1024)
    except Exception:
        return False

    offset = 0
    while offset < len(data) - 8:
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        if size < 8:
            break
        box_type = data[offset + 4 : offset + 8].decode("ascii", errors="ignore")
        if box_type == "moov":
            pos = offset + 8
            while pos < offset + size - 8:
                child_size = struct.unpack(">I", data[pos : pos + 4])[0]
                if child_size < 8:
                    break
                child_type = data[pos + 4 : pos + 8].decode("ascii", errors="ignore")
                if child_type == "trak":
                    p = pos + 8
                    while p < pos + child_size - 8:
                        sub_size = struct.unpack(">I", data[p : p + 4])[0]
                        if sub_size < 8:
                            break
                        sub_type = data[p + 4 : p + 8].decode("ascii", errors="ignore")
                        if sub_type == "mdia":
                            q = p + 8
                            while q < p + sub_size - 8:
                                hdlr_size = struct.unpack(">I", data[q : q + 4])[0]
                                if hdlr_size < 8:
                                    break
                                hdlr_type = data[q + 4 : q + 8].decode(
                                    "ascii", errors="ignore"
                                )
                                if hdlr_type == "hdlr":
                                    hdlr_data = data[q + 8 : q + hdlr_size]
                                    # version+flags, pre_defined, handler_type, reserved[12]
                                    name_start = q + 8 + 4 + 4 + 4 + 12
                                    name_end = hdlr_data.find(b"\x00", name_start - q)
                                    if name_end == -1:
                                        name_end = hdlr_size
                                    name = hdlr_data[
                                        name_start - q : name_end - q
                                    ].decode("ascii", errors="ignore")
                                    if "Twitter-vork" in name:
                                        return True
                                    break
                                q += hdlr_size
                            break
                        p += sub_size
                    break
                pos += child_size
            break
        offset += size
    return False


def remux_vork_video(input_path: str, output_path: str) -> None:
    """Remux a vork-muxed MP4 via double pass (MP4 -> MKV -> MP4)."""
    temp_path = input_path + ".temp.mkv"
    cmd1 = [
        "ffmpeg",
        "-i",
        input_path,
        "-map",
        "0",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        "-y",
        temp_path,
    ]
    proc = subprocess.run(cmd1, capture_output=True, text=True)
    if proc.returncode != 0:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise RuntimeError(f"FFmpeg first pass failed: {proc.stderr}")

    cmd2 = [
        "ffmpeg",
        "-i",
        temp_path,
        "-map",
        "0",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        "-y",
        output_path,
    ]
    proc = subprocess.run(cmd2, capture_output=True, text=True)
    if os.path.exists(temp_path):
        os.remove(temp_path)
    if proc.returncode != 0:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError(f"FFmpeg second pass failed: {proc.stderr}")


# ---------- Core extraction ----------
async def resolve_short_url(client: httpx.AsyncClient, short_url: str) -> str:
    """Follow t.co redirect and return the final tweet URL."""
    resp = await client.get(short_url, follow_redirects=True)
    resp.raise_for_status()
    return str(resp.url)


async def fetch_tweet_api(
    client: httpx.AsyncClient,
    tweet_id: str,
    cookies: dict[str, str],
) -> dict[str, Any]:
    """Fetch tweet data from the GraphQL API."""
    csrf_token = cookies.get("ct0")
    if not csrf_token:
        raise ValueError("Missing 'ct0' cookie – required for CSRF")

    api_headers = build_api_headers(csrf_token)
    query = build_api_query(tweet_id)
    url = f"{API_ENDPOINT}?{query}"
    headers = {**WEB_HEADERS, **api_headers}
    resp = await client.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"API {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def parse_tweet_response(raw_data: dict[str, Any]) -> TweetInfo:
    """Parse the API response and extract caption and media."""
    try:
        result = raw_data["data"]["tweetResult"]["result"]
    except KeyError:
        raise ValueError("Invalid API response: missing data.tweetResult.result")

    if result.get("__typename") == "TweetUnavailable":
        raise RuntimeError("Tweet is unavailable (deleted/private)")

    tweet = None
    if "tweet" in result and "legacy" in result["tweet"]:
        tweet = result["tweet"]["legacy"]
    elif "legacy" in result:
        tweet = result["legacy"]
    if not tweet:
        raise ValueError("No tweet data found")

    caption = sanitize_caption(tweet.get("full_text", ""))

    media_entities = []
    if "extended_entities" in tweet and "media" in tweet["extended_entities"]:
        media_entities = tweet["extended_entities"]["media"]
    elif "entities" in tweet and "media" in tweet["entities"]:
        media_entities = tweet["entities"]["media"]

    media_items = []
    for entity in media_entities:
        media_type = entity.get("type")
        if media_type == "photo":
            url = entity.get("media_url_https")
            if url:
                media_items.append(
                    MediaItem(
                        type="image",
                        thumbnail=url,
                        url=url,
                    )
                )
        elif media_type in ("video", "animated_gif"):
            variants = entity.get("video_info", {}).get("variants", [])
            formats = []
            for variant in variants:
                if variant.get("content_type") == "video/mp4":
                    url = variant.get("url", "")
                    if url:
                        w, h = parse_resolution_from_url(url)
                        formats.append(
                            MediaFormat(
                                url=url,
                                bitrate=variant.get("bitrate"),
                                width=w,
                                height=h,
                            )
                        )
            formats.sort(key=lambda f: f.bitrate or 0, reverse=True)
            duration_ms = entity.get("video_info", {}).get("duration_millis", 0)
            duration = duration_ms // 1000 if duration_ms else None
            media_items.append(
                MediaItem(
                    type="video",
                    thumbnail=entity.get("media_url_https"),
                    formats=formats,
                    duration=duration,
                )
            )
        else:
            _log_.debug(f"Skipping unknown media type: {media_type}")

    return TweetInfo(caption=caption, media=media_items)


async def extract_twitter(
    url: str,
    cookie_file: str | None = None,
) -> TweetInfo:
    """
    Extract media information from a Twitter/X tweet URL.

    Args:
        url:          Twitter/X tweet URL (full or t.co short).
        cookie_file:  Path to Netscape-format cookie file (must contain 'ct0').

    Returns:
        TweetInfo object with caption and list of media items.

    Raises:
        ValueError: Invalid URL or missing cookies.
        RuntimeError: API failure or tweet unavailable.
    """
    cookies = {}
    if cookie_file:
        jar = load_netscape_cookies(cookie_file)
        cookies = cookies_to_dict(jar)
    else:
        _log_.warning(
            "No cookie file provided; Twitter API will likely reject the request."
        )

    async with httpx.AsyncClient(
        cookies=cookies,
        follow_redirects=False,
        timeout=30.0,
    ) as client:
        if SHORT_URL_RE.search(url):
            url = await resolve_short_url(client, url)

        match = TWEET_URL_RE.search(url)
        if not match:
            raise ValueError(f"Not a valid Twitter/X URL: {url}")
        tweet_id = match.group("id")

        try:
            raw_data = await fetch_tweet_api(client, tweet_id, cookies)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise RuntimeError(
                    "Authentication failed. Check that your cookies are valid and include 'ct0'."
                ) from e
            raise

        return parse_tweet_response(raw_data)


async def download_twitter(
    url: str,
    output_dir: str = ".",
    cookie_file: str | None = None,
    quiet: bool = False,
    progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
) -> list[DownloadResult]:
    """
    Download all media from a Twitter/X tweet. Automatically remux vork-muxed videos.

    Args:
        url:          Twitter/X tweet URL.
        output_dir:   Directory to save files.
        cookie_file:  Path to Netscape-format cookie file.
        quiet:        Suppress console output.
        progress_callback: Async callback for download progress.

    Returns:
        List of DownloadResult objects (one per media item).
    """
    os.makedirs(output_dir, exist_ok=True)

    info = await extract_twitter(url, cookie_file)
    if not info.media:
        raise RuntimeError("No media found in tweet.")

    results = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for idx, media in enumerate(info.media):
            # Determine best URL and dimensions
            if media.type == "image":
                source_url = media.url
                width = height = None  # not available
                ext = "jpg"
            else:  # video
                if not media.formats:
                    continue
                # Pick best quality (highest bitrate)
                best = media.formats[0]
                source_url = best.url
                width = best.width
                height = best.height
                ext = "mp4"

            # Build filename: use tweet ID and index
            fname = f"tweet_{idx}{ext}"
            dest = os.path.join(output_dir, fname)

            if not quiet:
                print(f"\n[down] {fname}  ({media.type})")
            await _download_file(client, source_url, dest, progress_callback)

            # Vork detection and remux (only for videos)
            if media.type == "video" and is_vork_muxer(dest):
                if not quiet:
                    print("[vork] Detected vork-muxed video, remuxing...")
                try:
                    remuxed_dest = dest + ".remuxed.mp4"
                    await asyncio.to_thread(remux_vork_video, dest, remuxed_dest)
                    os.replace(remuxed_dest, dest)
                    if not quiet:
                        print("[vork] Remuxed successfully")
                except Exception as e:
                    _log_.error(f"Remux failed: {e}")
                    if not quiet:
                        print(f"[vork] Remux failed: {e}")

            results.append(
                DownloadResult(
                    local_path=dest,
                    caption=info.caption,
                    media_type=media.type,
                    source_url=source_url,
                    thumbnail_url=media.thumbnail or "",
                    width=width,
                    height=height,
                )
            )

            if idx < len(info.media) - 1:
                await asyncio.sleep(0.5)

    return results


async def _download_file(
    client: httpx.AsyncClient,
    url: str,
    dest: str,
    progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
) -> None:
    """Download a file with optional progress callback."""
    headers = {
        "User-Agent": WEB_HEADERS["User-Agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://x.com/",
        "Origin": "https://x.com",
    }
    async with client.stream("GET", url, headers=headers, timeout=60.0) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"Download failed: {resp.status_code}")
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        async with aiofiles.open(dest, "wb") as f:
            async for chunk in resp.aiter_bytes(chunk_size=256 * 1024):
                await f.write(chunk)
                done += len(chunk)
                if progress_callback:
                    await progress_callback(done, total, dest)
