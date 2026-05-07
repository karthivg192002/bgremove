import os
import uuid
import math
from collections import Counter

import numpy as np
from rembg import remove, new_session
from PIL import Image, ImageFilter, ImageDraw

from app.core.config import OUTPUT_DIR, WATERMARK_LOGO


# ── Rembg session — loaded once at import time ────────────────────────────────
_SESSION = new_session("u2net")


# ── Tamil Nadu Saree palette presets ─────────────────────────────────────────
PALETTE_PRESETS = [
    {"name": "rose_cream",   "hue": (340, 20),  "top": (255, 245, 245), "bottom": (240, 200, 200), "vignette": (200, 160, 160)},
    {"name": "ivory_blush",  "hue": (0,   20),  "top": (255, 250, 245), "bottom": (245, 215, 200), "vignette": (210, 170, 155)},
    {"name": "warm_sand",    "hue": (20,  45),  "top": (255, 248, 230), "bottom": (240, 215, 170), "vignette": (200, 170, 120)},
    {"name": "pale_gold",    "hue": (45,  65),  "top": (255, 252, 220), "bottom": (245, 225, 150), "vignette": (205, 180, 100)},
    {"name": "light_mint",   "hue": (65,  90),  "top": (240, 255, 235), "bottom": (200, 235, 200), "vignette": (155, 195, 155)},
    {"name": "soft_sage",    "hue": (90,  150), "top": (235, 250, 240), "bottom": (190, 230, 205), "vignette": (140, 190, 160)},
    {"name": "light_aqua",   "hue": (150, 200), "top": (230, 250, 255), "bottom": (180, 225, 240), "vignette": (130, 185, 205)},
    {"name": "pale_blue",    "hue": (200, 240), "top": (230, 240, 255), "bottom": (185, 205, 245), "vignette": (140, 165, 215)},
    {"name": "lavender",     "hue": (240, 290), "top": (245, 235, 255), "bottom": (215, 195, 245), "vignette": (170, 145, 210)},
    {"name": "soft_pink",    "hue": (290, 340), "top": (255, 235, 248), "bottom": (245, 195, 230), "vignette": (210, 150, 195)},
]

NEUTRAL_PRESET = {
    "name":     "neutral_white",
    "top":      (255, 255, 255),
    "bottom":   (235, 235, 240),
    "vignette": (195, 195, 205),
}


class BackgroundRemoveService:

    # ── Public entry point ────────────────────────────────────────────────────

    @staticmethod
    def remove_background_and_add_ecommerce_background(
        input_path: str,
        add_watermark: bool = True,
    ) -> str:
        output_filename = f"{uuid.uuid4().hex}.webp"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        # 1 ── Remove background (reuse cached session; no alpha_matting for speed)
        with Image.open(input_path) as img:
            img = img.convert("RGBA")
            subject: Image.Image = remove(img, session=_SESSION)

        # 2 ── Sharpen edges
        subject = subject.filter(
            ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3)
        )

        width, height = subject.size

        # 3 ── Pick background based on dominant colour
        preset = BackgroundRemoveService._pick_background_preset(subject)

        # 4 ── Build gradient + vignette background (numpy — no Python loops)
        background = BackgroundRemoveService._create_gradient(width, height, preset["top"], preset["bottom"])
        vignette   = BackgroundRemoveService._create_vignette(width, height, preset["vignette"])
        background = Image.alpha_composite(background, vignette)

        # 5 ── Composite subject
        result = Image.alpha_composite(background, subject)

        # 6 ── Rounded-corner white-bg watermark
        if add_watermark and os.path.exists(WATERMARK_LOGO):
            result = BackgroundRemoveService._add_rounded_watermark(result, WATERMARK_LOGO)

        # method=0 is the fastest WebP encoder; quality=85 keeps file size small
        result.save(output_path, format="WEBP", quality=85, method=0)
        return output_path

    # Backward-compat shim
    @staticmethod
    def remove_background_and_add_watermark(input_path: str) -> str:
        return BackgroundRemoveService.remove_background_and_add_ecommerce_background(input_path)

    # ── Dominant colour analysis ──────────────────────────────────────────────

    @staticmethod
    def _pick_background_preset(subject: Image.Image) -> dict:
        small = subject.resize((80, 80), Image.LANCZOS).convert("RGBA")
        pixels = list(small.getdata())

        opaque = [p[:3] for p in pixels if p[3] > 128]
        if not opaque:
            return NEUTRAL_PRESET

        hues = []
        for r, g, b in opaque:
            h, s, v = BackgroundRemoveService._rgb_to_hsv(r, g, b)
            if s > 0.15 and 0.15 < v < 0.95:
                hues.append(int(h))

        if not hues:
            return NEUTRAL_PRESET

        bucketed = [h // 10 * 10 for h in hues]
        dominant_hue = Counter(bucketed).most_common(1)[0][0]

        for preset in PALETTE_PRESETS:
            lo, hi = preset["hue"]
            if lo > hi:
                if dominant_hue >= lo or dominant_hue <= hi:
                    return preset
            else:
                if lo <= dominant_hue <= hi:
                    return preset

        return NEUTRAL_PRESET

    @staticmethod
    def _rgb_to_hsv(r: int, g: int, b: int):
        r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0
        cmax = max(r_, g_, b_)
        cmin = min(r_, g_, b_)
        delta = cmax - cmin

        if delta == 0:
            h = 0.0
        elif cmax == r_:
            h = 60 * (((g_ - b_) / delta) % 6)
        elif cmax == g_:
            h = 60 * (((b_ - r_) / delta) + 2)
        else:
            h = 60 * (((r_ - g_) / delta) + 4)

        s = 0.0 if cmax == 0 else delta / cmax
        return h, s, cmax

    # ── Background helpers (numpy — no per-pixel Python loops) ────────────────

    @staticmethod
    def _create_gradient(width: int, height: int, top_color: tuple, bottom_color: tuple) -> Image.Image:
        t = np.linspace(0, 1, height, dtype=np.float32)[:, np.newaxis]  # (H, 1)
        arr = np.empty((height, width, 4), dtype=np.uint8)
        for c in range(3):
            col = (top_color[c] + (bottom_color[c] - top_color[c]) * t).astype(np.uint8)
            arr[:, :, c] = np.broadcast_to(col, (height, width))
        arr[:, :, 3] = 255
        return Image.fromarray(arr, "RGBA")

    @staticmethod
    def _create_vignette(width: int, height: int, vignette_color: tuple, strength: float = 0.28) -> Image.Image:
        cx, cy = width / 2, height / 2
        x = np.arange(width,  dtype=np.float32)
        y = np.arange(height, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        dist = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
        alpha = np.clip(255 * strength * dist ** 2, 0, 255).astype(np.uint8)

        arr = np.empty((height, width, 4), dtype=np.uint8)
        arr[:, :, 0] = vignette_color[0]
        arr[:, :, 1] = vignette_color[1]
        arr[:, :, 2] = vignette_color[2]
        arr[:, :, 3] = alpha
        return Image.fromarray(arr, "RGBA")

    # ── Watermark ─────────────────────────────────────────────────────────────

    @staticmethod
    def _add_rounded_watermark(
        base_image: Image.Image,
        logo_path: str,
        bg_color: tuple = (255, 255, 255, 220),
        corner_radius_ratio: float = 0.22,
        padding_ratio: float = 0.18,
    ) -> Image.Image:
        logo = Image.open(logo_path).convert("RGBA")

        base_w, base_h = base_image.size

        target_logo_w = int(base_w * 0.15)
        scale = target_logo_w / logo.width
        target_logo_h = int(logo.height * scale)
        logo = logo.resize((target_logo_w, target_logo_h), Image.LANCZOS)

        padding  = int(max(target_logo_w, target_logo_h) * padding_ratio)
        bubble_w = target_logo_w + padding * 2
        bubble_h = target_logo_h + padding * 2
        radius   = int(bubble_h * corner_radius_ratio)

        bubble = Image.new("RGBA", (bubble_w, bubble_h), (0, 0, 0, 0))
        ImageDraw.Draw(bubble).rounded_rectangle(
            [(0, 0), (bubble_w - 1, bubble_h - 1)],
            radius=radius,
            fill=bg_color,
        )
        bubble.paste(logo, (padding, padding), logo)

        margin = int(base_w * 0.02)
        pos = (base_w - bubble_w - margin, base_h - bubble_h - margin)

        layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        layer.paste(bubble, pos, bubble)

        return Image.alpha_composite(base_image, layer)
