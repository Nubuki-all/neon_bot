import io
import os

import modal

app = modal.App("realesrgan-api")

# name -> (weights URL, sha256 or None). Any single-image SR model spandrel
# supports can go here (ESRGAN, Real-ESRGAN, SwinIR, HAT, DAT, DRCT, ...).
MODELS = {
    "x4plus": (
        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        None,
    ),
    "anime": (
        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
        None,
    ),
    # Official Real_HAT_GAN_sharper.pth; upstream only hosts it on Drive
    "hat": (
        "https://huggingface.co/anchuang/Real_HAT_GAN_SRx4_sharper/resolve/main/Real_HAT_GAN_sharper.pth",
        "5800b67136006eb8cab3b4ed7c8d73b6a195bb18e6cc709b674f9aa069c00271",
    ),
}
GFPGAN_URL = (
    "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"
)
DEFAULT_MODEL = "x4plus"
# Smaller tiles for heavy transformer models
TILE_SIZES = {"hat": 256}
# x4plus background + GFPGAN on faces; SUPIR runs in its own container
EXTRA_MODELS = ["face", "supir"]

SUPIR_COMMIT = "bda91af2000042f8bedfec8897d92917e67c1d88"
SUPIR_DIR = "/models/supir"
# Longest side SUPIR outputs; it upscales at most 2x
SUPIR_MAX_SIDE = 2048
SUPIR_A_PROMPT = (
    "Cinematic, High Contrast, highly detailed, taken using a Canon EOS R camera, "
    "hyper detailed photo - realistic maximum detail, 32k, Color Grading, ultra HD, "
    "extreme meticulous detailing, skin pore detailing, hyper sharpness, perfect without deformations."
)
SUPIR_N_PROMPT = (
    "painting, oil painting, illustration, drawing, art, sketch, oil painting, cartoon, "
    "CG Style, 3D render, unreal engine, blurring, dirty, messy, worst quality, low quality, "
    "frames, watermark, signature, jpeg artifacts, deformed, lowres, over-smooth"
)


def download_weights():
    import hashlib
    import urllib.request

    import torch
    from facexlib.utils.face_restoration_helper import FaceRestoreHelper

    os.makedirs("/models", exist_ok=True)
    for name, (url, sha256) in MODELS.items():
        path = f"/models/{name}.pth"
        urllib.request.urlretrieve(url, path)
        if sha256:
            with open(path, "rb") as f:
                digest = hashlib.file_digest(f, "sha256").hexdigest()
            if digest != sha256:
                raise RuntimeError(f"{name}: sha256 mismatch ({digest})")
    urllib.request.urlretrieve(GFPGAN_URL, "/models/gfpgan.pth")
    # Fetches the face detection and parsing weights into /models/facexlib
    FaceRestoreHelper(
        4,
        face_size=512,
        use_parse=True,
        device=torch.device("cpu"),
        model_rootpath="/models/facexlib",
    )


def download_supir_weights():
    from huggingface_hub import hf_hub_download, snapshot_download

    kw = {"local_dir_use_symlinks": False}
    hf_hub_download(
        "stabilityai/stable-diffusion-xl-base-1.0",
        "sd_xl_base_1.0_0.9vae.safetensors",
        local_dir=SUPIR_DIR,
        **kw,
    )
    hf_hub_download("camenduru/SUPIR", "SUPIR-v0Q.ckpt", local_dir=SUPIR_DIR, **kw)
    hf_hub_download(
        "laion/CLIP-ViT-bigG-14-laion2B-39B-b160k",
        "open_clip_pytorch_model.bin",
        local_dir=f"{SUPIR_DIR}/clip-bigg",
        **kw,
    )
    snapshot_download(
        "openai/clip-vit-large-patch14",
        local_dir=f"{SUPIR_DIR}/clip-vit-large-patch14",
        allow_patterns=["*.json", "*.txt", "pytorch_model.bin"],
        **kw,
    )


upscaler_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "torch",
        "torchvision",
        "numpy",
        "Pillow",
        "spandrel",
        "facexlib",
        "opencv-python-headless",
        "fastapi[standard]",
    )
    .run_function(download_weights)
)

# SUPIR pins old versions of most of its stack, so it gets an image of its own
supir_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "libgl1", "libglib2.0-0")
    .pip_install(
        "torch==2.1.2",
        "torchvision==0.16.2",
        "xformers==0.0.23.post1",
        "huggingface_hub==0.20.3",
        "hf_transfer",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .run_function(download_supir_weights)
    .run_commands(
        f"git clone https://github.com/Fanghua-Yu/SUPIR /SUPIR && git -C /SUPIR checkout {SUPIR_COMMIT}",
        "grep -vE '^(gradio|gradio_imageslider|gradio_client|wandb|torch|torchvision|triton|xformers|fsspec)[=>]'"
        " /SUPIR/requirements.txt > /tmp/req.txt",
        "pip install -r /tmp/req.txt huggingface_hub==0.20.3",
        f'printf \'%s\\n\' "LLAVA_CLIP_PATH = None" "LLAVA_MODEL_PATH = None"'
        f" \"SDXL_CLIP1_PATH = '{SUPIR_DIR}/clip-vit-large-patch14'\""
        f" \"SDXL_CLIP2_CKPT_PTH = '{SUPIR_DIR}/clip-bigg/open_clip_pytorch_model.bin'\""
        " > /SUPIR/CKPT_PTH.py",
        f"sed -i -e 's|^SDXL_CKPT:.*|SDXL_CKPT: {SUPIR_DIR}/sd_xl_base_1.0_0.9vae.safetensors|'"
        f" -e 's|^SUPIR_CKPT_Q:.*|SUPIR_CKPT_Q: {SUPIR_DIR}/SUPIR-v0Q.ckpt|'"
        " /SUPIR/options/SUPIR_v0.yaml",
    )
)


@app.cls(
    image=upscaler_image,
    # First one with free capacity; L4s are often all taken
    gpu=["L4", "A10G", "T4"],
    timeout=1800,
    secrets=[modal.Secret.from_name("upscaler-auth-token")],
)
class UpscalerAPI:
    @modal.enter()
    def load_models(self):
        import torch
        from facexlib.utils.face_restoration_helper import FaceRestoreHelper
        from spandrel import ModelLoader

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        cuda = self.device.type == "cuda"
        loader = ModelLoader(device=self.device)
        self.models = {}
        for name in MODELS:
            model = loader.load_from_file(f"/models/{name}.pth").eval()
            if cuda and model.supports_half:
                dtype = torch.float16
            # Real bf16 needs Ampere or newer; is_bf16_supported() also counts
            # emulation (T4)
            elif (
                cuda
                and model.supports_bfloat16
                and torch.cuda.get_device_capability() >= (8, 0)
            ):
                dtype = torch.bfloat16
            else:
                dtype = torch.float32
            self.models[name] = (model.to(dtype=dtype), dtype)
        self.gfpgan = loader.load_from_file("/models/gfpgan.pth").eval()
        self.face_helper = FaceRestoreHelper(
            4,
            face_size=512,
            use_parse=True,
            device=self.device,
            model_rootpath="/models/facexlib",
        )

    def _tiled(self, model, x, tile=512, pad=16):
        # Upscale in overlapping tiles so big images fit in GPU memory
        _, _, h, w = x.shape
        s = model.scale
        out = x.new_zeros(1, 3, h * s, w * s)
        for y0 in range(0, h, tile):
            for x0 in range(0, w, tile):
                y1, x1 = min(y0 + tile, h), min(x0 + tile, w)
                py0, px0 = max(y0 - pad, 0), max(x0 - pad, 0)
                py1, px1 = min(y1 + pad, h), min(x1 + pad, w)
                o = model(x[:, :, py0:py1, px0:px1])
                oy, ox = (y0 - py0) * s, (x0 - px0) * s
                out[:, :, y0 * s : y1 * s, x0 * s : x1 * s] = o[
                    :, :, oy : oy + (y1 - y0) * s, ox : ox + (x1 - x0) * s
                ]
        return out

    def _upscale(self, model_name, rgb):
        # rgb: HxWx3 uint8 array -> upscaled HxWx3 uint8 array
        import torch

        model, dtype = self.models[model_name]
        x = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)
        x = x.to(self.device, dtype=dtype) / 255.0
        with torch.inference_mode():
            y = self._tiled(model, x, tile=TILE_SIZES.get(model_name, 512))
        y = (y.float().clamp(0, 1) * 255).round().byte()
        return y[0].permute(1, 2, 0).cpu().numpy()

    def _restore_faces(self, rgb, bg):
        # Same steps as GFPGANer.enhance, with spandrel's GFPGAN and our own
        # background
        import cv2
        import torch

        helper = self.face_helper
        helper.clean_all()
        helper.read_image(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        helper.get_face_landmarks_5(only_center_face=False, eye_dist_threshold=5)
        helper.align_warp_face()
        for face in helper.cropped_faces:
            t = torch.from_numpy(face[:, :, ::-1].copy()).permute(2, 0, 1).unsqueeze(0)
            t = t.to(self.device, dtype=torch.float32) / 127.5 - 1
            with torch.inference_mode():
                o = self.gfpgan.model(t, return_rgb=False)[0]
            o = ((o[0].clamp(-1, 1) + 1) * 127.5).round().byte()
            helper.add_restored_face(o.permute(1, 2, 0).cpu().numpy()[:, :, ::-1])
        helper.get_inverse_affine(None)
        out = helper.paste_faces_to_input_image(
            upsample_img=cv2.cvtColor(bg, cv2.COLOR_RGB2BGR)
        )
        return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)

    @modal.method()
    def process_upscale(
        self, file_bytes: bytes, model_name: str = DEFAULT_MODEL
    ) -> bytes:
        import numpy as np
        from PIL import Image

        rgb = np.array(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
        if model_name == "face":
            out = self._restore_faces(rgb, self._upscale(DEFAULT_MODEL, rgb))
        else:
            out = self._upscale(model_name, rgb)

        output = io.BytesIO()
        Image.fromarray(out).save(output, format="png")
        return output.getvalue()


@app.cls(image=supir_image, gpu=["L40S", "A100-40GB", "A100-80GB"], timeout=1800)
class SupirAPI:
    @modal.enter()
    def load_model(self):
        import sys

        # SUPIR imports CKPT_PTH and reads options/ relative to its repo root
        os.chdir("/SUPIR")
        sys.path.insert(0, "/SUPIR")
        from SUPIR.util import convert_dtype, create_SUPIR_model

        model = create_SUPIR_model("options/SUPIR_v0.yaml", SUPIR_sign="Q").half()
        model.init_tile_vae(encoder_tile_size=512, decoder_tile_size=64)
        model.ae_dtype = convert_dtype("bf16")
        model.model.dtype = convert_dtype("fp16")
        self.model = model.to("cuda")

    @modal.method()
    def process_upscale(self, file_bytes: bytes) -> bytes:
        from PIL import Image
        from SUPIR.util import PIL2Tensor, Tensor2PIL

        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        scale = min(2.0, SUPIR_MAX_SIDE / max(image.size))
        lq, h0, w0 = PIL2Tensor(image, upsacle=scale, min_size=1024)
        lq = lq.unsqueeze(0).to("cuda")[:, :3, :, :]
        samples = self.model.batchify_sample(
            lq,
            [""],
            num_steps=50,
            restoration_scale=-1,
            s_churn=5,
            s_noise=1.01,
            cfg_scale=4.0,
            control_scale=1.0,
            seed=1234,
            num_samples=1,
            p_p=SUPIR_A_PROMPT,
            n_p=SUPIR_N_PROMPT,
            color_fix_type="Wavelet",
            use_linear_CFG=True,
            use_linear_control_scale=False,
            cfg_scale_start=1.0,
            control_scale_start=0.0,
        )

        output = io.BytesIO()
        Tensor2PIL(samples[0], h0, w0).save(output, format="png")
        return output.getvalue()


@app.function(
    image=upscaler_image,
    timeout=1800,
    secrets=[modal.Secret.from_name("upscaler-auth-token")],
)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, HTTPException, Request, Response, Security, status
    from fastapi.security import APIKeyHeader

    web_app = FastAPI()
    api_key_header = APIKeyHeader(name="Authorization", auto_error=True)
    upscaler = UpscalerAPI()
    supir = SupirAPI()

    def verify_token(api_key: str = Security(api_key_header)):
        expected_token = os.environ.get("API_TOKEN")
        token = api_key.removeprefix("Bearer ")
        if not expected_token or token != expected_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API Token",
            )
        return token

    @web_app.get("/models")
    async def list_models(token: str = Security(verify_token)):
        return {"default": DEFAULT_MODEL, "models": list(MODELS) + EXTRA_MODELS}

    @web_app.post("/")
    async def upscale_endpoint(request: Request, token: str = Security(verify_token)):
        file_bytes = await request.body()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="No image bytes provided")
        model_name = request.query_params.get("model", DEFAULT_MODEL)
        if model_name == "supir":
            output_bytes = await supir.process_upscale.remote.aio(file_bytes)
        elif model_name in MODELS or model_name in EXTRA_MODELS:
            output_bytes = await upscaler.process_upscale.remote.aio(
                file_bytes, model_name
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")
        return Response(content=output_bytes, media_type="image/png")

    return web_app
