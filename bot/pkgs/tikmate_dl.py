import asyncio
import os
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import aiofiles
import aiohttp
from bs4 import BeautifulSoup
from httpx import AsyncClient


@dataclass
class DownloadResult:
    local_path: str
    caption: str
    media_type: str  # "video" or "image"
    source_url: str
    thumbnail_url: str
    width: int | None = None
    height: int | None = None


class TikmateAsync(AsyncClient):
    BASE_URL = "https://tikmate.io/"

    def __init__(self) -> None:
        super().__init__()
        self.headers: dict[str, str] = {
            "referer": "https://tikmate.io/",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
        }

    async def get_media(self, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            # Fetch the token using httpx
            token_res = await self.get(self.BASE_URL)
            token_match = dict(
                re.findall('name="(token)" value="(.*?)"', token_res.text)
            )

            async with session.post(
                self.BASE_URL + "abc.php",
                data={"url": url, **token_match},
                headers={
                    "Origin": "https://tikmate.io",
                    "x-requested-with": "XMLHttpRequest",
                    **self.headers,
                },
            ) as media:
                return await media.text()

    async def _download_file(
        self,
        client: AsyncClient,
        url: str,
        dest: str,
        progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
    ) -> None:
        async with client.stream(
            "GET", url, headers=self.headers, follow_redirects=True
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

    async def decode_with_deno(self, html_res: str) -> str:
        script_match = re.search(r"<script>(.*?)</script>", html_res, re.DOTALL)
        if not script_match:
            return "No packed script found."

        packed_js = script_match.group(1)

        deno_script = f"""
        let intercepted = "";
        globalThis.eval = function(code) {{
            intercepted = code;
        }};

        {packed_js}

        console.log(intercepted);
        """

        process = await asyncio.create_subprocess_exec(
            "deno",
            "run",
            "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate(input=deno_script.encode("utf-8"))

        if process.returncode != 0:
            return f"Deno Error: {stderr.decode('utf-8').strip()}"

        return stdout.decode("utf-8").strip()

    async def download_tikmate(
        self,
        url: str,
        output_dir: str = ".",
        quiet: bool = False,
        progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
    ) -> list[DownloadResult]:
        packed_html = await self.get_media(url)
        decoded_html = await self.decode_with_deno(packed_html)
        res = parse_tiktok_media(decoded_html)
        items: list[DownloadResult] = []
        rand_id = uuid.uuid4()
        for i, r in enumerate(res):
            item = DownloadResult(
                local_path="",
                caption=r.get("caption", ""),
                media_type=r.get("media_type", "image"),
                source_url=r.get("source_url", ""),
                thumbnail_url=r.get("thumbnail_link", ""),
            )
            suffix = f"_{i}" if len(items) > 1 else ""
            ext = "mp4" if item.media_type == "video" else "jpg"
            fname = f"{rand_id}{suffix}.{ext}"
            dest = os.path.join(output_dir, fname)

            if not quiet:
                print(f"\n[down] {fname}  ({item.media_type})")
            await self._download_file(self, item.source_url, dest, progress_callback)
            item.local_path = dest
            if not quiet:
                print(f"[ok] -> {dest}")
            items.append(item)
            if i < len(res) - 1:
                await asyncio.sleep(0.5)
        return items


def parse_tiktok_media(decoded_html_page: str) -> list[dict]:
    """
    Extracts HTML and parses out all media items (photos and videos) along with the caption.
    Returns a list of dictionaries containing thumbnail_link, media_type, source_url, and caption.
    """
    media_items = []

    html_match = re.search(
        r'innerHTML\s*=\s*"(.*?)";\s*parent\.document', decoded_html_page, re.DOTALL
    )
    if html_match:
        raw_html = html_match.group(1).replace('\\"', '"')
    else:
        raw_html = decoded_html_page

    soup = BeautifulSoup(raw_html, "html.parser")

    caption_elem = soup.select_one(
        'div.videotikmate-middle p, .video-info p, p[itemprop="description"]'
    )
    caption = caption_elem.get_text(strip=True) if caption_elem else ""

    if not caption:
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if text and len(text) > 3:
                caption = text
                break

    cards = soup.select(".card")
    for card in cards:
        img_tag = card.select_one("img.card-img-top")
        download_tag = card.select_one("a.btn-main")

        if img_tag and download_tag:
            media_items.append(
                {
                    "media_type": "image",
                    "thumbnail_link": img_tag.get("src", ""),
                    "source_url": download_tag.get("href", ""),
                    "caption": caption,
                }
            )

    video_download_btn = soup.select_one("a.download-btn")

    if video_download_btn:
        thumbnail_tag = soup.select_one(
            '.thumbnail img, .image-tikmate img, img[alt="avatar"]'
        )
        thumbnail_link = thumbnail_tag.get("src", "") if thumbnail_tag else ""

        media_items.append(
            {
                "media_type": "video",
                "thumbnail_link": thumbnail_link,
                "source_url": video_download_btn.get("href", ""),
                "caption": caption,
            }
        )

    return media_items
