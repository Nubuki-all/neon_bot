import base64
import io
import os

import modal

app = modal.App("tldr-api")

# Two models, each in its own container on a 24 GB card, so a request only
# starts the one it needs: text goes to an 8B text model, and replied images
# (screenshots, posters, memes) to an 8B vision model that reads and answers
# in one go. In bf16 the vision model doesn't leave room for a usable context
# on these cards (bigger cards queue for longer), so it runs in FP8: natively
# on L4, and through vLLM's Marlin kernels on A10G.
TEXT_MODEL = "Qwen/Qwen3-8B"
TEXT_MODEL_DIR = "/models/qwen3"
VISION_MODEL = "Qwen/Qwen3-VL-8B-Instruct-FP8"
VISION_MODEL_DIR = "/models/qwen3-vl"
MAX_MODEL_LEN = 16384
# Tokens kept free in the context for the reply, and for the prompt and an
# image; the message's text is cut to fit what's left
MAX_REPLY_TOKENS = 700
PROMPT_AND_IMAGE_TOKENS = 1700
# Big images are scaled down to about this many pixels before the model
# sees them, which bounds how much of the context an image takes up
MAX_IMAGE_PIXELS = 1280 * 28 * 28

STYLE = (
    "Your reply is sent in a WhatsApp chat: write plain text. For emphasis use "
    "*single asterisks*, never **double**, and use • for bullet points; no "
    "headings, tables or links. Reply in the same language as the message. "
    "If there's an image, read any text in it and use what it shows."
)
PROMPTS = {
    "tldr": (
        "Summarise the message below. Start with a one or two sentence TL;DR. "
        "If it's long or covers several things, add up to five short bullet "
        "points with the key details. Don't add opinions or anything that "
        "isn't in it. "
    )
    + STYLE,
    "eli5": (
        "Explain the message below in simple, everyday words, as you would to "
        "a curious 12 year old. Explain any jargon, keep it short and don't "
        "add facts that aren't in it, unless they're needed to make sense of "
        "it. "
    )
    + STYLE,
}


def download_text_model():
    from huggingface_hub import snapshot_download

    snapshot_download(TEXT_MODEL, local_dir=TEXT_MODEL_DIR)


def download_vision_model():
    from huggingface_hub import snapshot_download

    snapshot_download(VISION_MODEL, local_dir=VISION_MODEL_DIR)


base_image = (
    modal.Image.debian_slim(python_version="3.12")
    # vLLM 0.11.0 doesn't cap transformers, and 5.x drops tokenizer attributes
    # it reads; 4.57 is the first with Qwen3-VL
    .pip_install(
        "vllm==0.11.0",
        "transformers==4.57.1",
        "Pillow",
        "hf_transfer",
        "fastapi[standard]",
    ).env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)
text_image = base_image.run_function(download_text_model)
vision_image = base_image.run_function(download_vision_model)


def load_llm(model_dir: str, **kwargs):
    from vllm import LLM

    return LLM(
        model=model_dir,
        max_model_len=MAX_MODEL_LEN,
        max_num_seqs=2,
        gpu_memory_utilization=0.92,
        # CUDA graphs take memory and add to every cold start
        enforce_eager=True,
        **kwargs,
    )


def run_llm(llm, mode: str, text: str, image: bytes | None = None, **chat_kwargs):
    from vllm import SamplingParams

    content = []
    if image:
        content.append(
            {"type": "image_url", "image_url": {"url": image_data_url(image)}}
        )
    tokenizer = llm.get_tokenizer()
    budget = MAX_MODEL_LEN - MAX_REPLY_TOKENS - PROMPT_AND_IMAGE_TOKENS
    tokens = tokenizer.encode(text)
    if len(tokens) > budget:
        text = tokenizer.decode(tokens[:budget]) + "\n[…cut off]"
    content.append({"type": "text", "text": text or "(no text, only the image)"})
    messages = [
        {"role": "system", "content": PROMPTS[mode]},
        {"role": "user", "content": content},
    ]
    params = SamplingParams(temperature=0.3, max_tokens=MAX_REPLY_TOKENS)
    result = llm.chat(messages, params, **chat_kwargs)
    # Markdown habits WhatsApp doesn't use: "  " line breaks and **bold**
    reply = result[0].outputs[0].text.replace("**", "*")
    return "\n".join(line.rstrip() for line in reply.strip().splitlines())


def image_data_url(image: bytes) -> str:
    from PIL import Image

    # Re-encoded, since stickers and documents come as webp, gif, ...
    # and scaled down here, so a big photo can't fill the context
    picture = Image.open(io.BytesIO(image)).convert("RGB")
    scale = (MAX_IMAGE_PIXELS / (picture.width * picture.height)) ** 0.5
    if scale < 1:
        picture = picture.resize(
            (int(picture.width * scale), int(picture.height * scale))
        )
    output = io.BytesIO()
    picture.save(output, format="png")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


@app.cls(
    image=text_image,
    # 24 GB cards; whichever has free capacity
    gpu=["L4", "A10G"],
    timeout=600,
)
class TextModel:
    @modal.enter()
    def load_model(self):
        self.llm = load_llm(TEXT_MODEL_DIR)

    @modal.method()
    def explain(self, mode: str, text: str) -> str:
        # Qwen3 writes out its reasoning first unless told not to, which
        # isn't needed here and would slow every reply
        return run_llm(
            self.llm, mode, text, chat_template_kwargs={"enable_thinking": False}
        )


@app.cls(
    image=vision_image,
    gpu=["L4", "A10G"],
    timeout=600,
)
class VisionModel:
    @modal.enter()
    def load_model(self):
        self.llm = load_llm(
            VISION_MODEL_DIR,
            # No video: vLLM otherwise reserves memory for one at startup
            limit_mm_per_prompt={"image": 1, "video": 0},
        )

    @modal.method()
    def explain(self, mode: str, text: str, image: bytes) -> str:
        return run_llm(self.llm, mode, text, image)


@app.function(
    image=base_image,
    timeout=600,
    secrets=[modal.Secret.from_name("tldr-auth-token")],
)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, HTTPException, Request, Security, status
    from fastapi.security import APIKeyHeader

    web_app = FastAPI()
    api_key_header = APIKeyHeader(name="Authorization", auto_error=True)
    text_model = TextModel()
    vision_model = VisionModel()

    def verify_token(api_key: str = Security(api_key_header)):
        expected_token = os.environ.get("API_TOKEN")
        token = api_key.removeprefix("Bearer ")
        if not expected_token or token != expected_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API Token",
            )
        return token

    # Body: {"mode": "tldr" | "eli5", "text": str, "image": base64 str | null}
    @web_app.post("/")
    async def explain_endpoint(request: Request, token: str = Security(verify_token)):
        body = await request.json()
        mode = body.get("mode", "tldr")
        if mode not in PROMPTS:
            raise HTTPException(status_code=400, detail=f"Unknown mode: {mode}")
        text = str(body.get("text") or "")
        image = body.get("image")
        image = base64.b64decode(image) if image else None
        if not (text.strip() or image):
            raise HTTPException(status_code=400, detail="No text or image provided")
        if image:
            reply = await vision_model.explain.remote.aio(mode, text, image)
        else:
            reply = await text_model.explain.remote.aio(mode, text)
        return {"text": reply}

    return web_app
