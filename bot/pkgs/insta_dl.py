import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional

import aiofiles
import aiohttp

GRAPHQL_ENDPOINT = "https://www.instagram.com/graphql/query/"
POLARIS_ACTION = "PolarisPostActionLoadPostQueryQuery"
DOC_ID = "8845758582119845"

IGRAM_API_BASE = "api.igram.world"
IGRAM_HOST = "api-wh.igram.world"
IGRAM_HMAC_KEY = "75f2d70d3724f98e4a7d1ffd0ba9cfd907f3ae2632ee159980e2c521bff62358"
IGRAM_STATIC_TS = 1771418815381

APP_ID = "936619743392459"
BLOKS_VERSION_ID = "6309c8d03d8a3f47a1658ba38b304a3f837142ef5f637ebf1f8f52d4b802951e"
ASBD_ID = "129477"
HIDDEN_STATE = "20126.HYP:instagram_web_pkg.2.1...0"
SESSION_INTERNAL = "7436540909012459023"
ROLLOUT_HASH = "1019933358"

WEB_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-GB,en;q=0.9",
    "Cache-Control": "max-age=0",
    "Dnt": "1",
    "Priority": "u=0, i",
    "Sec-Ch-Ua": 'Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": "macOS",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

EMBED_PATTERN = re.compile(
    r"new ServerJS\(\)\);s\.handle\(({.*?})\);requireLazy",
    re.DOTALL,
)

SHORTCODE_RE = re.compile(
    r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)"
)
STORY_RE = re.compile(r"instagram\.com/stories/([^/]+)/(\d+)")
SHARE_RE = re.compile(r"instagram\.com/share(?:/(?:reels?|video|s|p))?/(?P<id>[^/?]+)")


@dataclass
class DownloadResult:
    local_path: str
    caption: str
    media_type: str  # "video" or "image"
    source_url: str
    thumbnail_url: str
    width: Optional[int] = None
    height: Optional[int] = None


def random_base64(n_bytes: int) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(n_bytes)).rstrip(b"=").decode()


def random_alpha(n: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def is_valid_instagram_url(url: str) -> bool:
    """Returns True if the URL matches an Instagram post, reel, story, IGTV, or share link."""
    return bool(
        SHORTCODE_RE.search(url) or STORY_RE.search(url) or SHARE_RE.search(url)
    )


async def _resolve_share_url(session: aiohttp.ClientSession, share_url: str) -> str:
    """Follow the share redirect and return the final Instagram URL."""
    async with session.get(share_url, allow_redirects=False) as resp:
        if resp.status in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if location:
                return location
    # If no redirect, return original (fallback)
    return share_url


def _build_gql_request(shortcode: str):
    session_str = "::" + random_alpha(6)
    session_data = random_base64(8)
    csrf_token = random_base64(32)
    device_id = random_base64(24)
    machine_id = random_base64(24)
    dynamic_flags = random_base64(154)
    csr = random_base64(154)
    jazoest = str(secrets.randbelow(10000) + 1)
    timestamp = str(int(time.time()))

    cookies = "; ".join(
        [
            f"csrftoken={csrf_token}",
            f"ig_did={device_id}",
            "wd=1280x720",
            "dpr=2",
            f"mid={machine_id}",
            "ig_nrcb=1",
        ]
    )

    headers = {
        **WEB_HEADERS,
        "x-ig-app-id": APP_ID,
        "X-FB-LSD": session_data,
        "X-CSRFToken": csrf_token,
        "X-Bloks-Version-Id": BLOKS_VERSION_ID,
        "x-asbd-id": ASBD_ID,
        "cookie": cookies,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-FB-Friendly-Name": POLARIS_ACTION,
    }

    variables = json.dumps(
        {
            "shortcode": shortcode,
            "fetch_tagged_user_count": None,
            "hoisted_comment_id": None,
            "hoisted_reply_id": None,
        },
        separators=(",", ":"),
    )

    body = {
        "__d": "www",
        "__a": "1",
        "__s": session_str,
        "__hs": HIDDEN_STATE,
        "__req": "b",
        "__ccg": "EXCELLENT",
        "__rev": ROLLOUT_HASH,
        "__hsi": SESSION_INTERNAL,
        "__dyn": dynamic_flags,
        "__csr": csr,
        "__user": "0",
        "__comet_req": "7",
        "libav": "0",
        "dpr": "2",
        "lsd": session_data,
        "jazoest": jazoest,
        "__spin_r": ROLLOUT_HASH,
        "__spin_b": "trunk",
        "__spin_t": timestamp,
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": POLARIS_ACTION,
        "variables": variables,
        "server_timestamps": "true",
        "doc_id": DOC_ID,
    }

    return headers, urllib.parse.urlencode(body).encode()


async def _get_gql_media(session: aiohttp.ClientSession, shortcode: str) -> dict:
    headers, body = _build_gql_request(shortcode)
    async with session.post(GRAPHQL_ENDPOINT, data=body, headers=headers) as resp:
        resp.raise_for_status()
        data = await resp.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"GQL status not ok: {data.get('status')}")
    media = data.get("data", {}).get("shortcode_media")
    if not media:
        raise RuntimeError("shortcode_media is None in GQL response")
    return media


def _traverse_json(obj, key: str):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = _traverse_json(v, key)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _traverse_json(item, key)
            if result is not None:
                return result
    return None


async def _get_embed_media(session: aiohttp.ClientSession, shortcode: str) -> dict:
    embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned"
    async with session.get(embed_url, headers=WEB_HEADERS) as resp:
        resp.raise_for_status()
        body = await resp.text()

    match = EMBED_PATTERN.search(body)
    if not match:
        raise RuntimeError("ServerJS JSON blob not found in embed page")

    raw_json = match.group(1)
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        raw_json = re.sub(r",\s*([}\]])", r"\1", raw_json)
        data = json.loads(raw_json)

    ctx_json_raw = _traverse_json(data, "contextJSON")
    if ctx_json_raw is None:
        raise RuntimeError("contextJSON not found in ServerJS blob")

    if isinstance(ctx_json_raw, str):
        ctx_json = json.loads(ctx_json_raw)
    else:
        raise RuntimeError(f"Unexpected contextJSON type: {
                type(ctx_json_raw)}")

    gql_data = ctx_json.get("gql_data")
    if not gql_data:
        raise RuntimeError("gql_data not found in contextJSON")

    media = gql_data.get("shortcode_media")
    if not media:
        raise RuntimeError("shortcode_media not found in gql_data")
    return media


async def _igram_get_server_time(session: aiohttp.ClientSession) -> int:
    try:
        async with session.get(f"https://{IGRAM_API_BASE}/msec") as resp:
            result = await resp.json()
            return int(result["msec"] * 1000)
    except Exception:
        return int(time.time() * 1000)


def _igram_sign(partial: dict, ts: int) -> str:
    json_str = json.dumps(partial, sort_keys=True, separators=(",", ":"))
    data_str = json_str + str(ts)
    key = bytes.fromhex(IGRAM_HMAC_KEY)
    return hmac.new(key, data_str.encode(), hashlib.sha256).hexdigest()


async def _igram_build_payload(
    session: aiohttp.ClientSession, url_params: dict
) -> bytes:
    now_ms = int(time.time() * 1000)
    server_ms = await _igram_get_server_time(session)
    drift = server_ms - now_ms
    correction = drift if abs(drift) >= 60000 else 0
    ts = now_ms + correction
    partial = {"_sc": 0, "_ef": 0, "_df": 0, **url_params}
    sig = _igram_sign(partial, ts)
    final = {
        **partial,
        "ts": ts,
        "_ts": IGRAM_STATIC_TS,
        "_tsc": correction,
        "_sv": 2,
        "_s": sig,
    }
    return json.dumps(final, separators=(",", ":")).encode()


def _get_cdn_url(igram_url: str) -> str:
    """Extract the real CDN URL from igram's redirector."""
    parsed = urllib.parse.urlparse(igram_url)
    params = urllib.parse.parse_qs(parsed.query)
    cdn = params.get("uri", [None])[0]
    if not cdn:
        raise RuntimeError(f"No 'uri' param in igram URL: {igram_url}")
    return cdn


async def _get_igram_media(session: aiohttp.ClientSession, shortcode: str) -> list:
    content_url = f"https://www.instagram.com/p/{shortcode}/"
    payload = await _igram_build_payload(session, {"target_url": content_url})
    headers = {
        "Content-Type": "application/json",
        "Referer": "https://igram.world/",
        "User-Agent": WEB_HEADERS["User-Agent"],
    }
    async with session.post(
        f"https://{IGRAM_HOST}/api/convert", data=payload, headers=headers
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()

    if isinstance(data, list):
        return data
    if data.get("success") is False:
        raise RuntimeError("igram returned success=false")
    return [data]


async def _get_igram_story(
    session: aiohttp.ClientSession, story_url: str
) -> DownloadResult:
    payload = await _igram_build_payload(session, {"url": story_url})
    headers = {
        "Content-Type": "application/json",
        "Referer": "https://igram.world/",
        "User-Agent": WEB_HEADERS["User-Agent"],
    }
    async with session.post(
        f"https://{IGRAM_HOST}/api/v1/instagram/story", data=payload, headers=headers
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()

    result = data.get("result")
    if not result or len(result) == 0:
        raise RuntimeError("No story result")

    story = result[0]
    is_video = bool(story.get("video_versions"))

    if is_video:
        # pick best quality by height
        videos = sorted(
            story["video_versions"], key=lambda v: v["height"], reverse=True
        )
        best = videos[0]
        source_url = best["url"]
        width, height = best.get("width", 0), best.get("height", 0)
        media_type = "video"
    else:
        # pick best candidate from image_versions2.candidates
        candidates = story["image_versions2"]["candidates"]
        best = max(candidates, key=lambda c: c.get("width", 0) * c.get("height", 0))
        source_url = best["url"]
        width, height = best.get("width", 0), best.get("height", 0)
        media_type = "image"

    return DownloadResult(
        local_path="",  # set after download
        caption="",
        media_type=media_type,
        source_url=source_url,
        thumbnail_url=source_url,
        width=width,
        height=height,
    )


#  Media parsing (posts/reels/IGTV)


def _parse_gql_media(data: dict) -> List[DownloadResult]:
    caption = ""
    for edge in data.get("edge_media_to_caption", {}).get("edges", []):
        caption = edge.get("node", {}).get("text", "")
        break

    typename = data.get("__typename", "")
    items = []

    if typename in ("GraphVideo", "XDTGraphVideo"):
        video_url = data["video_url"]
        display_url = data.get("display_url", "")
        items.append(
            DownloadResult(
                local_path="",
                caption=caption,
                media_type="video",
                source_url=video_url,
                thumbnail_url=display_url,
                width=data.get("dimensions", {}).get("width"),
                height=data.get("dimensions", {}).get("height"),
            )
        )
    elif typename in ("GraphImage", "XDTGraphImage"):
        url = data["display_url"]
        items.append(
            DownloadResult(
                local_path="",
                caption=caption,
                media_type="image",
                source_url=url,
                thumbnail_url=url,
            )
        )
    elif typename in ("GraphSidecar", "XDTGraphSidecar"):
        for edge in data.get("edge_sidecar_to_children", {}).get("edges", []):
            node = edge.get("node", {})
            node_type = node.get("__typename", "")
            if node_type in ("GraphVideo", "XDTGraphVideo"):
                video_url = node["video_url"]
                display_url = node.get("display_url", "")
                items.append(
                    DownloadResult(
                        local_path="",
                        caption=caption,
                        media_type="video",
                        source_url=video_url,
                        thumbnail_url=display_url,
                        width=node.get("dimensions", {}).get("width"),
                        height=node.get("dimensions", {}).get("height"),
                    )
                )
            elif node_type in ("GraphImage", "XDTGraphImage"):
                url = node["display_url"]
                items.append(
                    DownloadResult(
                        local_path="",
                        caption=caption,
                        media_type="image",
                        source_url=url,
                        thumbnail_url=url,
                    )
                )
    return items


def _parse_igram_items(raw_items: list) -> List[DownloadResult]:
    results = []
    for obj in raw_items:
        if not obj.get("url"):
            continue
        url_obj = obj["url"][0]
        cdn_url = _get_cdn_url(url_obj["url"])
        thumb_url = _get_cdn_url(obj.get("thumb", url_obj["url"]))
        ext = url_obj.get("ext", "")
        if ext == "mp4":
            results.append(
                DownloadResult(
                    local_path="",
                    caption="",
                    media_type="video",
                    source_url=cdn_url,
                    thumbnail_url=thumb_url,
                )
            )
        elif ext in ("jpg", "jpeg", "png", "webp", "heic"):
            results.append(
                DownloadResult(
                    local_path="",
                    caption="",
                    media_type="image",
                    source_url=cdn_url,
                    thumbnail_url=thumb_url,
                )
            )
    return results


async def _download_file(
    session: aiohttp.ClientSession,
    url: str,
    dest: str,
    progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
) -> None:
    headers = {
        "User-Agent": WEB_HEADERS["User-Agent"],
        "Referer": "https://www.instagram.com/",
    }
    async with session.get(url, headers=headers) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        async with aiofiles.open(dest, "wb") as f:
            async for chunk in resp.content.iter_chunked(65536):
                await f.write(chunk)
                done += len(chunk)
                if progress_callback:
                    await progress_callback(done, total, dest)


async def download_instagram(
    url: str,
    output_dir: str = ".",
    quiet: bool = False,
    progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
) -> List[DownloadResult]:
    """
    Download media from any Instagram URL (post, reel, IGTV, story, share).

    Args:
        url:        Full Instagram URL.
        output_dir: Directory to save files.
        quiet:      Suppress console progress.
        progress_callback: Async callback (downloaded_bytes, total_bytes, file_path).

    Returns:
        List of DownloadResult objects.
    """
    os.makedirs(output_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        # 1. Handle share URLs
        if SHARE_RE.search(url):
            if not quiet:
                print("[share] Resolving share URL...")
            url = await _resolve_share_url(session, url)
            if not quiet:
                print(f"[share] Resolved to {url}")

        # 2. Detect story
        story_match = STORY_RE.search(url)
        if story_match:
            username, story_id = story_match.groups()
            if not quiet:
                print(f"[story] Downloading story {story_id} from {username}")
            item = await _get_igram_story(session, url)
            # Download the story
            ext = "mp4" if item.media_type == "video" else "jpg"
            fname = f"story_{username}_{story_id}.{ext}"
            dest = os.path.join(output_dir, fname)
            if not quiet:
                print(f"[down] {fname}  ({item.media_type})")
            await _download_file(session, item.source_url, dest, progress_callback)
            item.local_path = dest
            if not quiet:
                print(f"[ok] -> {dest}")
            return [item]

        # 3. Post / reel / IGTV
        shortcode_match = SHORTCODE_RE.search(url)
        if not shortcode_match:
            raise ValueError(f"Not a supported Instagram URL: {url}")
        shortcode = shortcode_match.group(1)

        if not quiet:
            print(f"[*] Shortcode: {shortcode}")

        items = []

        # Extraction Method 1: GQL
        if not quiet:
            print("[1] Trying GQL Web API...")
        try:
            media = await _get_gql_media(session, shortcode)
            items = _parse_gql_media(media)
            if not quiet:
                print("[1] Success")
        except Exception as e:
            if not quiet:
                print(f"[1] Failed: {e}")

        # Extraction Method 2: Embed
        if not items:
            if not quiet:
                print("[2] Trying embed page...")
            try:
                media = await _get_embed_media(session, shortcode)
                items = _parse_gql_media(media)
                if not quiet:
                    print("[2] Success")
            except Exception as e:
                if not quiet:
                    print(f"[2] Failed: {e}")

        # Extraction Method 3: igram.world (posts)
        if not items:
            if not quiet:
                print("[3] Trying igram.world...")
            try:
                raw = await _get_igram_media(session, shortcode)
                items = _parse_igram_items(raw)
                if not quiet:
                    print("[3] Success")
            except Exception as e:
                if not quiet:
                    print(f"[3] Failed: {e}")

        if not items:
            raise RuntimeError("All three methods failed.")

        # Download each item
        for i, item in enumerate(items):
            suffix = f"_{i}" if len(items) > 1 else ""
            ext = "mp4" if item.media_type == "video" else "jpg"
            fname = f"{shortcode}{suffix}.{ext}"
            dest = os.path.join(output_dir, fname)

            if not quiet:
                print(f"\n[down] {fname}  ({item.media_type})")
            await _download_file(session, item.source_url, dest, progress_callback)
            item.local_path = dest
            if not quiet:
                print(f"[ok] -> {dest}")
            if i < len(items) - 1:
                await asyncio.sleep(0.5)

        return items
