import asyncio
import json
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional

import aiofiles
import aiohttp

PIN_RESOURCE_ENDPOINT = "https://www.pinterest.com/resource/PinResource/get/"
SHORTENER_API_FORMAT = "https://api.pinterest.com/url_shortener/{}/redirect/"

PINTEREST_HEADERS = {
    "X-Pinterest-Pws-Handler": "www/[username].js",  # static header from govd
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
}

SHORT_PIN_RE = re.compile(
    r"https?://(?:www\.)?pin\.(?:it|co|com|de|es|fr|uk|ca|mx|br|jp|in|nz|au|se|no|dk|fi|nl|be|at|ch)/(?P<id>\w+)"
)
FULL_PIN_RE = re.compile(
    r"https?://(?:[^/]+\.)?pinterest\.[^/]+/pin/(?:[\w-]+--)?(?P<id>\d+)"
)


@dataclass
class DownloadResult:
    local_path: str
    caption: str
    media_type: str  # "video" or "image"
    source_url: str
    thumbnail_url: str
    width: Optional[int] = None
    height: Optional[int] = None


def is_valid_pinterest_url(url: str) -> bool:
    """Return True if the URL matches a Pinterest pin (full or short)."""
    return bool(FULL_PIN_RE.search(url) or SHORT_PIN_RE.search(url))


async def _resolve_short_url(session: aiohttp.ClientSession, short_id: str) -> str:
    """Follow the shortener redirect and return the full Pinterest pin URL."""
    api_url = SHORTENER_API_FORMAT.format(short_id)
    async with session.get(api_url, allow_redirects=False) as resp:
        if resp.status in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if location:
                return location
    raise RuntimeError(f"Failed to resolve short URL for id {short_id}")


def _pick_best_non_hls_video(video_list: dict) -> Optional[dict]:
    """
    From a video_list map (e.g. {"V_720P": {...}, "V_HLS": {...}}),
    pick the non‑HLS entry with the highest height. Returns the full dict.
    """
    best = None
    best_height = -1
    for key, info in video_list.items():
        if "HLS" in key:
            continue  # skip HLS playlists
        h = info.get("height", 0)
        if h > best_height:
            best_height = h
            best = info
    return best


def _parse_pin_data(pin_data: dict) -> List[DownloadResult]:
    """
    Extract media from a PinData JSON object.
    Returns a list of DownloadResult (usually one item).
    """
    caption = pin_data.get("title", "").strip()
    # 1. Standard video
    videos = pin_data.get("videos")
    if videos and "video_list" in videos:
        best = _pick_best_non_hls_video(videos["video_list"])
        if best:
            return [
                DownloadResult(
                    local_path="",
                    caption=caption,
                    media_type="video",
                    source_url=best["url"],
                    thumbnail_url=best.get("thumbnail", best["url"]),
                    width=best.get("width"),
                    height=best.get("height"),
                )
            ]

    # 2. Story pin (pages → blocks or page‑level image)
    story = pin_data.get("story_pin_data")
    if story and "pages" in story:
        for page in story["pages"]:
            # Check blocks first (block_type = 3 is video)
            for block in page.get("blocks", []):
                if block.get("block_type") == 3 and block.get("video"):
                    vid_list = block["video"].get("video_list", {})
                    best = _pick_best_non_hls_video(vid_list)
                    if best:
                        return [
                            DownloadResult(
                                local_path="",
                                caption=caption,
                                media_type="video",
                                source_url=best["url"],
                                thumbnail_url=best.get("thumbnail", best["url"]),
                                width=best.get("width"),
                                height=best.get("height"),
                            )
                        ]

            # Check page‑level image
            page_img = page.get("image")
            if page_img:
                originals = page_img.get("images", {}).get("originals")
                if originals:
                    return [
                        DownloadResult(
                            local_path="",
                            caption=caption,
                            media_type="image",
                            source_url=originals["url"],
                            thumbnail_url=originals["url"],
                            width=originals.get("width"),
                            height=originals.get("height"),
                        )
                    ]

    # 3. Standard image (orig)
    images = pin_data.get("images")
    if images and images.get("orig"):
        orig = images["orig"]
        return [
            DownloadResult(
                local_path="",
                caption=caption,
                media_type="image",
                source_url=orig["url"],
                thumbnail_url=orig["url"],
                width=orig.get("width"),
                height=orig.get("height"),
            )
        ]

    # 4. Embed GIF (treated as video)
    embed = pin_data.get("embed")
    if embed and embed.get("type") == "gif":
        return [
            DownloadResult(
                local_path="",
                caption=caption,
                media_type="video",  # GIF is saved as .mp4
                source_url=embed["src"],
                thumbnail_url=embed["src"],
            )
        ]

    return []  # nothing found


async def _download_file(
    session: aiohttp.ClientSession,
    url: str,
    dest: str,
    progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
) -> None:
    headers = {
        "User-Agent": PINTEREST_HEADERS["User-Agent"],
        "Referer": "https://www.pinterest.com/",
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


async def download_pinterest(
    url: str,
    output_dir: str = ".",
    quiet: bool = False,
    progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
) -> List[DownloadResult]:
    """
    Download media from a Pinterest pin URL.

    Args:
        url:        Pinterest pin URL (full or short).
        output_dir: Directory to save the file(s).
        quiet:      Suppress console output.
        progress_callback:
            Async callable (downloaded_bytes, total_bytes, file_path)
            called after each chunk.

    Returns:
        List of DownloadResult objects (usually one item).
    """
    os.makedirs(output_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        # Resolve short URLs
        short_match = SHORT_PIN_RE.search(url)
        if short_match:
            short_id = short_match.group("id")
            if not quiet:
                print(f"[short] Resolving short pin ID: {short_id}")
            url = await _resolve_short_url(session, short_id)
            if not quiet:
                print(f"[short] Resolved to {url}")

        # Extract pin ID
        full_match = FULL_PIN_RE.search(url)
        if not full_match:
            raise ValueError(f"Not a supported Pinterest pin URL: {url}")
        pin_id = full_match.group("id")

        if not quiet:
            print(f"[*] Pin ID: {pin_id}")

        # Build API request
        payload = json.dumps(
            {
                "options": {
                    "field_set_key": "unauth_react_main_pin",
                    "id": pin_id,
                }
            },
            separators=(",", ":"),
        )
        params = urllib.parse.urlencode({"data": payload})
        api_url = f"{PIN_RESOURCE_ENDPOINT}?{params}"

        # Fetch pin data
        try:
            async with session.get(api_url, headers=PINTEREST_HEADERS) as resp:
                resp.raise_for_status()
                pin_response = await resp.json()
        except aiohttp.ClientResponseError as e:
            raise RuntimeError(f"Pinterest API error: {e}")

        resource = pin_response.get("resource_response")
        if not resource:
            raise RuntimeError("No resource_response in Pinterest API reply")
        pin_data = resource.get("data")
        if not pin_data:
            raise RuntimeError("Empty pin data")

        # Parse media items
        items = _parse_pin_data(pin_data)
        if not items:
            raise RuntimeError("No downloadable media found (only HLS or missing)")

        # Download each item (usually one)
        for i, item in enumerate(items):
            suffix = f"_{i}" if len(items) > 1 else ""
            ext = "mp4" if item.media_type == "video" else "jpg"
            fname = f"{pin_id}{suffix}.{ext}"
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
