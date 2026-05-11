import asyncio
import json
import logging
import os
import re
import traceback
from dataclasses import dataclass
from http.cookiejar import Cookie, CookieJar
from typing import Optional, List, Callable, Awaitable
from urllib.parse import urlparse, parse_qs

import aiofiles
import httpx

_log_ = logging.getLogger(__name__)


VIDEO_URL_BASE = "https://www.tiktok.com/@_/video/"

WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": (
        '"Chromium";v="136", '
        '"Google Chrome";v="136", '
        '"Not.A/Brand";v="99"'
    ),
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

SHORT_TIKTOK_RE = re.compile(
    r"https?://((?:vm|vt|www)\.)?(vx)?tiktok\.com/(?:t/)?(?P<id>[a-zA-Z0-9-]+)"
)

FULL_TIKTOK_RE = re.compile(
    r"https?://((?:www|m)\.)?(vx)?tiktok\.com/"
    r"(embed/|@[^/]+/)?(video|photo)/(?P<id>\d+)"
)


@dataclass
class DownloadResult:
    local_path: str
    caption: str
    media_type: str
    source_url: str
    thumbnail_url: str
    width: Optional[int] = None
    height: Optional[int] = None



def is_valid_tiktok_url(url: str) -> bool:
    return bool(FULL_TIKTOK_RE.search(url) or SHORT_TIKTOK_RE.search(url))


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



def _load_netscape_cookies(filepath: str) -> CookieJar:
    """Load Netscape-format cookies into a CookieJar usable by httpx."""
    jar = CookieJar()

    with open(filepath, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) != 7:
                continue

            raw_domain, flag, path, secure, expires, name, value = parts

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


async def _resolve_short_url(client: httpx.AsyncClient, short_url: str) -> str:
    """
    Follow the VM/VT short link and return the real video/photo URL.
    Handles geo-blocked login pages with 'redirect_url' parameter.
    """
    resp = await client.get(short_url, follow_redirects=True)
    url = str(resp.url)
    parsed = urlparse(url)
    if parsed.path == "/login":
        params = parse_qs(parsed.query)
        redirect_target = params.get("redirect_url", [None])[0]
        if redirect_target:
            return redirect_target
        raise RuntimeError("Geo-restricted content – cookies or VPN required")
    return url


async def _fetch_tiktok_page(client: httpx.AsyncClient, video_id: str) -> tuple[dict, dict]:
    """
    Fetch the TikTok page and return the parsed itemStruct and the response cookies.
    Retries up to 5 times with a fixed 1‑second delay.
    """
    url = f"{VIDEO_URL_BASE}{video_id}"
    last_exc = None
    for _ in range(5):
        try:
            resp = await client.get(url, headers=WEB_HEADERS)
            resp.raise_for_status()
            if resp.url.path == "/login":
                raise RuntimeError("Login page returned – cookies may be expired")
            body = resp.text
            item_struct = _parse_universal_data(body)
            # Convert httpx.Cookies to a plain dict for easy reuse
            response_cookies = dict(resp.cookies.items())
            return item_struct, response_cookies
        except Exception as e:
            last_exc = e
            await asyncio.sleep(1)
    raise last_exc


def _parse_universal_data(html: str) -> dict:
    """Extract the itemStruct from the __UNIVERSAL_DATA_FOR_REHYDRATION__ JSON."""
    match = re.search(
        r'<script[^>]*id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
        html, re.DOTALL,
    )
    if not match:
        raise RuntimeError("Universal data script not found")
    data = json.loads(match.group(1))
    default_scope = _traverse_json(data, "__DEFAULT_SCOPE__")
    if not default_scope:
        raise RuntimeError("__DEFAULT_SCOPE__ not found")
    item_struct = _traverse_json(default_scope, "itemStruct")
    if not item_struct:
        raise RuntimeError("itemStruct not found (video may be unavailable)")
    return item_struct


def _parse_tiktok_item(item: dict) -> List[DownloadResult]:
    """Convert the raw itemStruct into a list of DownloadResult objects."""
    caption = item.get("desc", "").strip()

    # Photo slides
    if item.get("imagePost"):
        images = item["imagePost"].get("images", [])
        results = []
        for img in images:
            url_list = img.get("imageURL", {}).get("urlList", [])
            if url_list:
                results.append(DownloadResult(
                    local_path="",
                    caption=caption,
                    media_type="image",
                    source_url=url_list[-1],
                    thumbnail_url=url_list[-1],
                ))
        return results

    # Single video
    video = item.get("video")
    if video and "PlayAddrStruct" in video:
        play_addr = video["PlayAddrStruct"]
        url_list = play_addr.get("UrlList", [])
        if url_list:
            return [DownloadResult(
                local_path="",
                caption=caption,
                media_type="video",
                source_url=url_list[-1],
                thumbnail_url="",
                width=play_addr.get("Width"),
                height=play_addr.get("Height"),
            )]
    return []


async def _download_media(
    url: str,
    dest: str,
    referer: str,
    cookies: dict,
    progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
) -> None:
    """Download a video/image using httpx with HTTP/2 and correct headers."""
    headers = {
        "User-Agent": WEB_HEADERS["User-Agent"],
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
        "Origin": "https://www.tiktok.com",
        "Connection": "keep-alive",
    }
    async with httpx.AsyncClient(http2=True, follow_redirects=True, cookies=cookies) as client:
        async with client.stream("GET", url, headers=headers, timeout=60.0) as resp:
            if resp.status_code not in (200, 206):
                error_body = await resp.aread()
                raise RuntimeError(f"Download failed ({resp.status_code}): {error_body[:500]}")
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            async with aiofiles.open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=256 * 1024):
                    await f.write(chunk)
                    done += len(chunk)
                    if progress_callback:
                        await progress_callback(done, total, dest)


async def download_tiktok(
    url: str,
    output_dir: str = ".",
    quiet: bool = False,
    progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
    cookie_file: Optional[str] = None,
) -> List[DownloadResult]:
    """
    Download media from a TikTok URL.

    Args:
        url:               TikTok video/photo/short URL.
        output_dir:        Directory to save files.
        quiet:             Suppress console output.
        progress_callback: Async callback (downloaded_bytes, total_bytes, file_path).
        cookie_file:       Path to a Netscape-format cookie file (bypasses geo-locks).

    Returns:
        List of DownloadResult objects.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Load cookies from file (if provided)
    client_cookies = None
    if cookie_file:
        client_cookies = _load_netscape_cookies(cookie_file)

    # Create a single httpx client for all initial requests
    async with httpx.AsyncClient(http2=True, follow_redirects=False, cookies=client_cookies) as client:
        # Resolve short URLs
        short_match = SHORT_TIKTOK_RE.search(url)
        if short_match:
            if not quiet:
                print(f"[short] resolving: {url}")
            url = await _resolve_short_url(client, url)
            if not quiet:
                print(f"[short] -> {url}")

        full_match = FULL_TIKTOK_RE.search(url)
        if not full_match:
            raise ValueError(f"Unsupported TikTok URL: {url}")
        media_id = full_match.group("id")

        if not quiet:
            print(f"[*] media id: {media_id}")

        # Fetch page and parse
        try:
            item_struct, response_cookies = await _fetch_tiktok_page(client, media_id)
        except Exception as e:
            _log_.error(traceback.format_exc())
            raise RuntimeError(f"Failed to fetch page: {e}")

        items = _parse_tiktok_item(item_struct)
        if not items:
            raise RuntimeError("No media found (private/deleted/geo-blocked)")

        # Download each media item
        for i, item in enumerate(items):
            suffix = f"_{i}" if len(items) > 1 else ""
            ext = "mp4" if item.media_type == "video" else "jpg"
            fname = f"{media_id}{suffix}.{ext}"
            dest = os.path.join(output_dir, fname)

            if not quiet:
                print(f"\n[down] {fname}  ({item.media_type})")
            await _download_media(item.source_url, dest, referer=url,
                                  cookies=response_cookies, progress_callback=progress_callback)
            item.local_path = dest
            if not quiet:
                print(f"[ok] -> {dest}")
            if i < len(items) - 1:
                await asyncio.sleep(0.5)

    return items
