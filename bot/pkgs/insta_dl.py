import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
import traceback
import urllib.parse
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import aiofiles
import httpx

GRAPHQL_ENDPOINT = "https://www.instagram.com/graphql/query/"
POLARIS_ACTION = "PolarisPostRootQuery"
DOC_ID = "28077897148546091"

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

_log_ = logging.getLogger(__name__)

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
    width: int | None = None
    height: int | None = None


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


def _canonical_instagram_url(original_url: str, shortcode: str) -> str:
    """Preserve the original path type: /p/, /reel/, /tv/"""
    match = re.search(
        r"(https?://[^/]+/(?:p|reel|reels|tv)/[A-Za-z0-9_-]+)", original_url
    )
    if match:
        return match.group(1) + "/"
    return f"https://www.instagram.com/p/{shortcode}/"


async def _resolve_share_url(client: httpx.AsyncClient, share_url: str) -> str:
    """Follow the share redirect and return the final Instagram URL."""
    resp = await client.get(share_url, follow_redirects=False)
    if resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("Location")
        if location:
            return location
    return share_url


def _get_number_from_query(name: str, data: str):
    match = re.search(rf"{re.escape(name)}=(\d+)", data or "")
    return int(match.group(1)) if match else None


def _get_object_from_entries(name: str, data: str):
    match = re.search(rf'\["{re.escape(name)}",.*?,({{.*?}}),\d+\]', data or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


async def _get_gql_params(client: httpx.AsyncClient, shortcode: str):
    resp = await client.get(
        f"https://www.instagram.com/p/{shortcode}/",
        headers=WEB_HEADERS,
        follow_redirects=True,
    )
    resp.raise_for_status()
    html = resp.text

    site_data = _get_object_from_entries("SiteData", html)
    polaris_site_data = _get_object_from_entries("PolarisSiteData", html)
    web_config = _get_object_from_entries("DGWWebConfig", html)
    push_info = _get_object_from_entries("InstagramWebPushInfo", html)
    security_config = _get_object_from_entries("InstagramSecurityConfig", html)
    bloks = _get_object_from_entries("WebBloksVersioningID", html)
    lsd_data = _get_object_from_entries("LSD", html)

    lsd = lsd_data.get("token") if isinstance(lsd_data, dict) else None
    lsd = lsd or random_base64(8)
    csrf = (
        security_config.get("csrf_token") if isinstance(security_config, dict) else None
    )
    app_id = web_config.get("appId") if isinstance(web_config, dict) else None
    app_id = app_id or APP_ID
    bloks_version = bloks.get("versioningID") if isinstance(bloks, dict) else None
    bloks_version = bloks_version or BLOKS_VERSION_ID

    device_id = (
        polaris_site_data.get("device_id")
        if isinstance(polaris_site_data, dict)
        else None
    )
    machine_id = (
        polaris_site_data.get("machine_id")
        if isinstance(polaris_site_data, dict)
        else None
    )
    anon_cookie = "; ".join(
        x
        for x in [
            f"csrftoken={csrf}" if csrf else None,
            f"ig_did={device_id}" if device_id else None,
            "wd=1280x720",
            "dpr=2",
            f"mid={machine_id}" if machine_id else None,
            "ig_nrcb=1",
        ]
        if x
    )

    rollout_hash = (
        push_info.get("rollout_hash") if isinstance(push_info, dict) else None
    )
    rollout_hash = rollout_hash or ROLLOUT_HASH
    haste_session = (
        site_data.get("haste_session") if isinstance(site_data, dict) else None
    )
    haste_session = haste_session or HIDDEN_STATE
    hsi = site_data.get("hsi") if isinstance(site_data, dict) else None
    hsi = hsi or SESSION_INTERNAL
    spin_r = site_data.get("__spin_r") if isinstance(site_data, dict) else None
    spin_r = spin_r or rollout_hash
    spin_b = site_data.get("__spin_b") if isinstance(site_data, dict) else None
    spin_b = spin_b or "trunk"
    spin_t = site_data.get("__spin_t") if isinstance(site_data, dict) else None
    spin_t = spin_t or int(time.time())

    headers = {
        **WEB_HEADERS,
        "x-ig-app-id": app_id,
        "X-FB-LSD": lsd,
        "X-CSRFToken": csrf or "",
        "X-Bloks-Version-Id": bloks_version,
        "x-asbd-id": ASBD_ID,
        "cookie": anon_cookie,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-FB-Friendly-Name": POLARIS_ACTION,
    }
    body = {
        "__d": "www",
        "__a": "1",
        "__s": "::" + random_alpha(6),
        "__hs": haste_session,
        "__req": "b",
        "__ccg": "EXCELLENT",
        "__rev": rollout_hash,
        "__hsi": hsi,
        "__dyn": random_base64(154),
        "__csr": random_base64(154),
        "__user": "0",
        "__comet_req": _get_number_from_query("__comet_req", html) or 7,
        "av": "0",
        "dpr": "2",
        "lsd": lsd,
        "jazoest": _get_number_from_query("jazoest", html)
        or secrets.randbelow(10000) + 1,
        "__spin_r": spin_r,
        "__spin_b": spin_b,
        "__spin_t": spin_t,
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": POLARIS_ACTION,
        "variables": json.dumps(
            {
                "shortcode": shortcode,
                "__relay_internal__pv__PolarisShortDramaEnabledrelayprovider": True,
                "__relay_internal__pv__PolarisMultiCaptionCarouselEnabledrelayprovider": True,
            },
            separators=(",", ":"),
        ),
        "server_timestamps": "true",
        "doc_id": DOC_ID,
    }
    return headers, body


async def _get_gql_media(client: httpx.AsyncClient, shortcode: str) -> dict:
    headers, body = await _get_gql_params(client, shortcode)
    resp = await client.post(
        GRAPHQL_ENDPOINT, data=urllib.parse.urlencode(body).encode(), headers=headers
    )
    resp.raise_for_status()
    data = resp.json()

    items = (
        data.get("data", {})
        .get("xdt_api__v1__media__shortcode__web_info", {})
        .get("items")
    )
    if not items:
        raise RuntimeError(
            "xdt_api__v1__media__shortcode__web_info items not found in GQL response"
        )

    return items[0]


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


async def _get_embed_media(client: httpx.AsyncClient, shortcode: str) -> dict:
    embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned"
    resp = await client.get(embed_url, headers=WEB_HEADERS)
    resp.raise_for_status()
    body = resp.text

    patterns = [
        re.compile(r'"init",\[\],\[(.*?)\]\],', re.DOTALL),
        re.compile(r"new ServerJS\(\)\);s\.handle\(({.*?})\);requireLazy", re.DOTALL),
    ]
    raw_json = None
    for pattern in patterns:
        match = pattern.search(body)
        if match:
            raw_json = match.group(1)
            break
    if raw_json is None:
        raise RuntimeError("Embedded JSON blob not found in embed page")

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

    media = gql_data.get("shortcode_media") or gql_data.get("xdt_shortcode_media")
    if not media:
        raise RuntimeError("shortcode_media/xdt_shortcode_media not found in gql_data")
    return media



def _get_cdn_url(igram_url: str) -> str:
    parsed = urllib.parse.urlparse(igram_url)
    params = urllib.parse.parse_qs(parsed.query)
    cdn = params.get("uri", [None])[0]
    if not cdn:
        raise RuntimeError(f"No 'uri' param in igram URL: {igram_url}")
    return cdn




def _parse_new_media(data: dict) -> list[DownloadResult]:
    """Parses the new xdt_api__v1__media__shortcode__web_info response format"""
    caption_dict = data.get("caption") or {}
    caption = caption_dict.get("text", "")
    items = []

    carousel = data.get("carousel_media")
    if carousel:
        for item in carousel:
            if not item.get("image_versions2"):
                continue

            is_video = bool(item.get("video_versions"))
            candidates = item["image_versions2"].get("candidates", [])
            thumb = candidates[0]["url"] if candidates else ""

            if is_video:
                videos = sorted(
                    item["video_versions"],
                    key=lambda v: v.get("width", 0) * v.get("height", 0),
                    reverse=True,
                )
                best_video = videos[0]
                items.append(
                    DownloadResult(
                        local_path="",
                        caption=caption,
                        media_type="video",
                        source_url=best_video["url"],
                        thumbnail_url=thumb,
                        width=best_video.get("width"),
                        height=best_video.get("height"),
                    )
                )
            else:
                best_img = (
                    max(
                        candidates, key=lambda c: c.get("width", 0) * c.get("height", 0)
                    )
                    if candidates
                    else None
                )
                if best_img:
                    items.append(
                        DownloadResult(
                            local_path="",
                            caption=caption,
                            media_type="image",
                            source_url=best_img["url"],
                            thumbnail_url=thumb,
                            width=best_img.get("width"),
                            height=best_img.get("height"),
                        )
                    )
        return items

    if data.get("video_versions"):
        videos = sorted(
            data["video_versions"],
            key=lambda v: v.get("width", 0) * v.get("height", 0),
            reverse=True,
        )
        best_video = videos[0]
        candidates = data.get("image_versions2", {}).get("candidates", [])
        thumb = candidates[0]["url"] if candidates else ""

        items.append(
            DownloadResult(
                local_path="",
                caption=caption,
                media_type="video",
                source_url=best_video["url"],
                thumbnail_url=thumb,
                width=best_video.get("width"),
                height=best_video.get("height"),
            )
        )
        return items

    if data.get("image_versions2", {}).get("candidates"):
        candidates = data["image_versions2"]["candidates"]
        best_img = max(candidates, key=lambda c: c.get("width", 0) * c.get("height", 0))
        thumb = candidates[0]["url"] if candidates else ""

        items.append(
            DownloadResult(
                local_path="",
                caption=caption,
                media_type="image",
                source_url=best_img["url"],
                thumbnail_url=thumb,
                width=best_img.get("width"),
                height=best_img.get("height"),
            )
        )
        return items

    return items


def _parse_gql_media(data: dict) -> list[DownloadResult]:
    """Parses the old shortcode_media format used by the embed HTML fallback"""
    caption = ""
    for edge in data.get("edge_media_to_caption", {}).get("edges", []):
        caption = edge.get("node", {}).get("text", "")
        break

    items = []

    sidecar = data.get("edge_sidecar_to_children", {}).get("edges", [])
    if sidecar:
        for edge in sidecar:
            node = edge.get("node", {})
            if node.get("video_url"):
                items.append(
                    DownloadResult(
                        local_path="",
                        caption=caption,
                        media_type="video",
                        source_url=node["video_url"],
                        thumbnail_url=node.get("display_url", ""),
                        width=node.get("dimensions", {}).get("width"),
                        height=node.get("dimensions", {}).get("height"),
                    )
                )
            elif node.get("display_url"):
                items.append(
                    DownloadResult(
                        local_path="",
                        caption=caption,
                        media_type="image",
                        source_url=node["display_url"],
                        thumbnail_url=node["display_url"],
                    )
                )
        return items

    if data.get("video_url"):
        items.append(
            DownloadResult(
                local_path="",
                caption=caption,
                media_type="video",
                source_url=data["video_url"],
                thumbnail_url=data.get("display_url", ""),
                width=data.get("dimensions", {}).get("width"),
                height=data.get("dimensions", {}).get("height"),
            )
        )
        return items
    if data.get("is_video"):
        items.append(
            DownloadResult(
                local_path="",
                caption=caption,
                media_type="video",
                source_url="",
                thumbnail_url="",
            )
        )
        return items

    if data.get("display_url"):
        items.append(
            DownloadResult(
                local_path="",
                caption=caption,
                media_type="image",
                source_url=data["display_url"],
                thumbnail_url=data["display_url"],
            )
        )
        return items

    return items


def _parse_igram_items(raw_items: list) -> list[DownloadResult]:
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
    client: httpx.AsyncClient,
    url: str,
    dest: str,
    progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
) -> None:
    headers = {
        "User-Agent": WEB_HEADERS["User-Agent"],
        "Referer": "https://www.instagram.com/",
    }
    async with client.stream(
        "GET", url, headers=headers, follow_redirects=True
    ) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        async with aiofiles.open(dest, "wb") as f:
            async for chunk in resp.aiter_bytes(chunk_size=65536):
                await f.write(chunk)
                done += len(chunk)
                if progress_callback:
                    await progress_callback(done, total, dest)


async def download_instagram(
    url: str,
    output_dir: str = ".",
    quiet: bool = False,
    progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
) -> list[DownloadResult]:
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

    def _result_to_items(res: dict, caption: str = "") -> list[DownloadResult]:
        items: list[DownloadResult] = []
        for r in res:
            if not r.get("url"):
                continue
            items.append(
                DownloadResult(
                    local_path="",
                    caption=caption,
                    media_type=r.get("type", "image"),
                    source_url=r.get("url"),
                    thumbnail_url=r.get("thumbnail", ""),
                )
            )
        return items

    async with httpx.AsyncClient(
        http2=True, timeout=30.0, follow_redirects=False
    ) as client:
        # 1. Handle share URLs
        if SHARE_RE.search(url):
            if not quiet:
                print("[share] Resolving share URL...")
            url = await _resolve_share_url(client, url)
            if not quiet:
                print(f"[share] Resolved to {url}")

        # 2. Detect story
        story_match = STORY_RE.search(url)
        if story_match:
            username, story_id = story_match.groups()
            if not quiet:
                print(f"[story] Downloading story {story_id} from {username}")
            res = await try_snapsave(url)
            item = _result_to_items(res)[0]
            ext = "mp4" if item.media_type == "video" else "jpg"
            fname = f"story_{username}_{story_id}.{ext}"
            dest = os.path.join(output_dir, fname)
            if not quiet:
                print(f"[down] {fname}  ({item.media_type})")
            await _download_file(client, item.source_url, dest, progress_callback)
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
            media = await _get_gql_media(client, shortcode)
            items = _parse_new_media(media)
            if not quiet:
                print("[1] Success")
        except Exception as e:
            _log_.error(traceback.format_exc())
            if not quiet:
                print(f"[1] Failed: {e}")

        # Extraction Method 2: Embed
        if not items:
            if not quiet:
                print("[2] Trying embed page...")
            try:
                media = await _get_embed_media(client, shortcode)
                items = _parse_gql_media(media)
                if items and not items[0].source_url:
                    res = await try_snapsave(url)
                    caption = items[0].caption
                    items = _result_to_items(res, caption)

                if not quiet:
                    print("[2] Success")
            except Exception as e:
                _log_.error(traceback.format_exc())
                if not quiet:
                    print(f"[2] Failed: {e}")

        # Extraction Method 3
        if not items:
            if not quiet:
                print("[3] Trying external extractor...")
            try:
                # raw = await _get_igram_media(client, url, shortcode, max_retries=2)
                # items = _parse_igram_items(raw)
                res = await try_snapsave(url)
                items = _result_to_items(res)
                if not quiet:
                    print("[3] Success")
            except Exception as e:
                _log_.error(traceback.format_exc())
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
            await _download_file(client, item.source_url, dest, progress_callback)
            item.local_path = dest
            if not quiet:
                print(f"[ok] -> {dest}")
            if i < len(items) - 1:
                await asyncio.sleep(0.5)

        return items


UA_BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"


def parse_download_html(html: str) -> list:
    if not html or not isinstance(html, str):
        return []

    results = []
    seen_urls = set()

    video_pattern = (
        r'href=\\?["\'](https?://[^"\'\\]+/v2\?token=[^"\'\\]+|[^"\'\\]+\.mp4[^"\'\\]*)'
    )
    video_matches = re.finditer(video_pattern, html)
    video_urls = []
    for m in video_matches:
        u = m.group(1).replace("&amp;", "&").replace("\\u0026", "&")
        if u and u not in seen_urls:
            seen_urls.add(u)
            video_urls.append(u)

    thumb_pattern = r'src=\\?["\'](https?://[^"\'\\]+/thumb\?token=[^"\'\\]+|[^"\'\\]+\.jpg[^"\'\\]*)'
    thumb_matches = re.finditer(thumb_pattern, html)
    thumb_urls = []
    for m in thumb_matches:
        u = m.group(1).replace("&amp;", "&").replace("\\u0026", "&")
        if u and u not in seen_urls:
            seen_urls.add(u)
            thumb_urls.append(u)

    if video_urls:
        for i, v_url in enumerate(video_urls):
            item = {"url": v_url, "type": "video"}
            if i < len(thumb_urls):
                item["thumbnail"] = thumb_urls[i]
            results.append(item)
    else:
        img_patterns = [
            r'href=\\?["\'](https?://[^"\'\\]+\.jpg[^"\'\\]*)',
            r'"url"\s*:\s*"(https?://[^"]+\.jpg[^"]*)"',
        ]
        for pat in img_patterns:
            for match in re.finditer(pat, html):
                u = match.group(1).replace("&amp;", "&").replace("\\u0026", "&")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    results.append({"url": u, "type": "image"})

    return results


async def deobfuscate_with_deno(raw_js: str) -> str:
    js_code = f"""
    const raw = {json.dumps(raw_js)};
    const fakeEvalHolder = {{ val: '' }};
    const patched = raw.replace(/\\beval\\s*\\(/, 'fakeEvalHolder.val=(');
    try {{
        const fn = new Function('fakeEvalHolder', patched);
        fn(fakeEvalHolder);
    }} catch (e) {{}}

    const output = fakeEvalHolder.val || raw;
    Deno.stdout.writeSync(new TextEncoder().encode(output));
    """

    process = await asyncio.create_subprocess_exec(
        "deno",
        "run",
        "-",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate(input=js_code.encode("utf-8"))

    if process.returncode == 0 and stdout:
        return stdout.decode("utf-8")

    return raw_js


async def try_snapsave(url: str) -> list:
    async with httpx.AsyncClient() as client:
        await client.get(
            "https://snapsave.app/", headers={"User-Agent": UA_BROWSER}, timeout=10.0
        )

        cookie_str = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://snapsave.app/",
            "Origin": "https://snapsave.app",
            "User-Agent": UA_BROWSER,
        }
        if cookie_str:
            headers["Cookie"] = cookie_str

        r2 = await client.post(
            "https://snapsave.app/action.php",
            data={"url": url},
            headers=headers,
            timeout=15.0,
        )

        raw = r2.text if isinstance(r2.text, str) else json.dumps(r2.text)

        decoded = raw
        if "eval(" in raw:
            decoded = await deobfuscate_with_deno(raw)

        if "Unable to connect" in decoded or "error_api" in decoded:
            raise RuntimeError("snapsave: Instagram blocked")

        items = parse_download_html(decoded)

        if not items:
            raise RuntimeError("snapsave: no media found")

        return items
