import asyncio

import httpx

from bot.config import conf

# Optional /upscale models served by the Modal API, besides its default
UPSCALE_MODELS = {
    "anime": "Real-ESRGAN anime, for drawings and anime",
    "hat": "HAT, for real photos",
    "face": "GFPGAN, restores faces",
    "supir": "[Owner | Sudo] SUPIR, rebuilds badly degraded photos (slow)",
}


def unknown_model_msg(model: str) -> str:
    models = "\n".join(f"- {k}: {v}" for k, v in UPSCALE_MODELS.items())
    return f"*Unknown model:* {model}\n\n*Models:*\n{models}"


async def upscale_single_image(
    client: httpx.AsyncClient,
    image_bytes: bytes,
    api_url: str,
    api_token: str,
    model: str | None = None,
) -> bytes:
    headers = {"Authorization": f"Bearer {api_token}"}
    params = {"model": model} if model else None

    response = await client.post(
        api_url, content=image_bytes, headers=headers, params=params
    )

    response.raise_for_status()

    return response.content


async def upscale_batch(
    images_bytes: list[bytes], timeout_seconds: float = 120.0, model: str | None = None
) -> list[bytes]:
    """
    Upscales a batch of image bytes concurrently using Modal's auto-scaling infrastructure.
    model picks the upscaler (see UPSCALE_MODELS); None uses the API's default.

    Raises:
        httpx.HTTPStatusError: If the server returns a 4xx/5xx status code.
        httpx.RequestError: If a network connection issue or timeout occurs.
    """
    api_url = conf.MODAL_UPSCALE_API
    api_token = conf.MODAL_UPSCALE_TOKEN
    timeout = httpx.Timeout(timeout_seconds)

    # Reuse a single AsyncClient connection pool for maximum performance
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        tasks = [
            upscale_single_image(client, img_bytes, api_url, api_token, model)
            for img_bytes in images_bytes
        ]

        upscaled_results = await asyncio.gather(*tasks)
        return list(upscaled_results)
