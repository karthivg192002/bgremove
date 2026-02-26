from rembg import remove
from PIL import Image, ImageFilter, ImageDraw
import uuid
import os
import math
from collections import Counter

from app.core.config import OUTPUT_DIR, WATERMARK_LOGO


# ── Tamil Nadu Saree palette presets ─────────────────────────────────────────
# hue: (low, high) degrees — wrapping supported for reds (e.g. 340-20)
PALETTE_PRESETS = [
    {
        "name": "rose_cream",
        "hue": (340, 20),           # deep reds / magentas wrapping 360
        "top":     (255, 245, 245),
        "bottom":  (240, 200, 200),
        "vignette":(200, 160, 160),
    },
    {
        "name": "ivory_blush",
        "hue": (0, 20),             # red-orange
        "top":     (255, 250, 245),
        "bottom":  (245, 215, 200),
        "vignette":(210, 170, 155),
    },
    {
        "name": "warm_sand",
        "hue": (20, 45),            # orange / rust
        "top":     (255, 248, 230),
        "bottom":  (240, 215, 170),
        "vignette":(200, 170, 120),
    },
    {
        "name": "pale_gold",
        "hue": (45, 65),            # yellow / gold
        "top":     (255, 252, 220),
        "bottom":  (245, 225, 150),
        "vignette":(205, 180, 100),
    },
    {
        "name": "light_mint",
        "hue": (65, 90),            # yellow-green
        "top":     (240, 255, 235),
        "bottom":  (200, 235, 200),
        "vignette":(155, 195, 155),
    },
    {
        "name": "soft_sage",
        "hue": (90, 150),           # green
        "top":     (235, 250, 240),
        "bottom":  (190, 230, 205),
        "vignette":(140, 190, 160),
    },
    {
        "name": "light_aqua",
        "hue": (150, 200),          # teal / cyan
        "top":     (230, 250, 255),
        "bottom":  (180, 225, 240),
        "vignette":(130, 185, 205),
    },
    {
        "name": "pale_blue",
        "hue": (200, 240),          # blue
        "top":     (230, 240, 255),
        "bottom":  (185, 205, 245),
        "vignette":(140, 165, 215),
    },
    {
        "name": "lavender",
        "hue": (240, 290),          # violet / purple
        "top":     (245, 235, 255),
        "bottom":  (215, 195, 245),
        "vignette":(170, 145, 210),
    },
    {
        "name": "soft_pink",
        "hue": (290, 340),          # pink / hot-pink
        "top":     (255, 235, 248),
        "bottom":  (245, 195, 230),
        "vignette":(210, 150, 195),
    },
]

NEUTRAL_PRESET = {
    "name":    "neutral_white",
    "top":     (255, 255, 255),
    "bottom":  (235, 235, 240),
    "vignette":(195, 195, 205),
}


class BackgroundRemoveService:

    # ── Public entry point ────────────────────────────────────────────────────

    @staticmethod
    def remove_background_and_add_ecommerce_background(
        input_path: str,
        add_watermark: bool = True,
    ) -> str:
        """
        Full pipeline:
          1. Remove background with rembg.
          2. Analyse subject's dominant hue.
          3. Auto-select a complementary light gradient background.
          4. Apply vignette for studio look.
          5. Composite subject over background.
          6. Optionally add a rounded white-bg watermark.

        Returns path to the saved output PNG.
        """
        output_filename = f"{uuid.uuid4().hex}.png"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        # 1 ── Remove background
        with Image.open(input_path) as img:
            img = img.convert("RGBA")
            subject: Image.Image = remove(
                img,
                alpha_matting=True,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10,
            )

        # 2 ── Sharpen edges
        subject = subject.filter(
            ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3)
        )

        width, height = subject.size

        # 3 ── Pick background based on image dominant colour
        preset = BackgroundRemoveService._pick_background_preset(subject)

        # 4 ── Build gradient + vignette background
        background = BackgroundRemoveService._create_gradient(
            width, height, preset["top"], preset["bottom"]
        )
        vignette = BackgroundRemoveService._create_vignette(
            width, height, preset["vignette"]
        )
        background = Image.alpha_composite(background, vignette)

        # 5 ── Composite subject
        result = Image.alpha_composite(background, subject)

        # 6 ── Rounded-corner white-bg watermark
        if add_watermark and os.path.exists(WATERMARK_LOGO):
            result = BackgroundRemoveService._add_rounded_watermark(
                result, WATERMARK_LOGO
            )

        result.save(output_path, format="PNG", compress_level=0)
        return output_path

    # Backward-compat shim
    @staticmethod
    def remove_background_and_add_watermark(input_path: str) -> str:
        return BackgroundRemoveService.remove_background_and_add_ecommerce_background(
            input_path
        )

    # ── Dominant colour analysis ──────────────────────────────────────────────

    @staticmethod
    def _pick_background_preset(subject: Image.Image) -> dict:
        """
        Downsample the subject, collect hues from opaque mid-tone pixels,
        find the most common hue bucket and return the matching preset.
        """
        small = subject.resize((80, 80), Image.LANCZOS).convert("RGBA")
        pixels = list(small.getdata())

        opaque = [p[:3] for p in pixels if p[3] > 128]
        if not opaque:
            return NEUTRAL_PRESET

        hues = []
        for r, g, b in opaque:
            h, s, v = BackgroundRemoveService._rgb_to_hsv(r, g, b)
            # Ignore very dark, very light, or washed-out pixels
            if s > 0.15 and 0.15 < v < 0.95:
                hues.append(int(h))

        if not hues:
            return NEUTRAL_PRESET

        # 10-degree hue buckets
        bucketed = [h // 10 * 10 for h in hues]
        dominant_hue = Counter(bucketed).most_common(1)[0][0]

        for preset in PALETTE_PRESETS:
            lo, hi = preset["hue"]
            if lo > hi:                              # wraps around 360°
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

    # ── Background helpers ────────────────────────────────────────────────────

    @staticmethod
    def _create_gradient(
        width: int,
        height: int,
        top_color: tuple,
        bottom_color: tuple,
    ) -> Image.Image:
        """Smooth top-to-bottom vertical gradient."""
        base = Image.new("RGBA", (width, height))
        draw = ImageDraw.Draw(base)
        for y in range(height):
            t = y / max(height - 1, 1)
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
        return base

    @staticmethod
    def _create_vignette(
        width: int,
        height: int,
        vignette_color: tuple,
        strength: float = 0.28,
    ) -> Image.Image:
        """Radial vignette — darkens corners for a studio-photograph feel."""
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        cx, cy = width / 2, height / 2
        # Step by 2 px for speed; the feathering hides gaps
        for x in range(0, width, 2):
            for y in range(0, height, 2):
                dist = math.sqrt(((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2)
                alpha = int(min(255, 255 * strength * (dist ** 2)))
                draw.point((x, y), fill=(*vignette_color, alpha))
        return layer

    # ── Watermark ─────────────────────────────────────────────────────────────

    @staticmethod
    def _add_rounded_watermark(
        base_image: Image.Image,
        logo_path: str,
        bg_color: tuple = (255, 255, 255, 220),   # white, slightly transparent
        corner_radius_ratio: float = 0.22,
        padding_ratio: float = 0.18,
    ) -> Image.Image:
        """
        Renders the logo inside a rounded-rectangle white pill bubble,
        then composites it at the bottom-right of base_image.
        """
        logo = Image.open(logo_path).convert("RGBA")

        base_w, base_h = base_image.size

        # Scale logo to 15 % of base width
        target_logo_w = int(base_w * 0.15)
        scale = target_logo_w / logo.width
        target_logo_h = int(logo.height * scale)
        logo = logo.resize((target_logo_w, target_logo_h), Image.LANCZOS)

        padding = int(max(target_logo_w, target_logo_h) * padding_ratio)
        bubble_w = target_logo_w + padding * 2
        bubble_h = target_logo_h + padding * 2
        radius   = int(bubble_h * corner_radius_ratio)

        # White rounded-rectangle background
        bubble = Image.new("RGBA", (bubble_w, bubble_h), (0, 0, 0, 0))
        ImageDraw.Draw(bubble).rounded_rectangle(
            [(0, 0), (bubble_w - 1, bubble_h - 1)],
            radius=radius,
            fill=bg_color,
        )

        # Centre the logo inside the bubble
        bubble.paste(logo, (padding, padding), logo)

        # Place at bottom-right with 2 % margin
        margin = int(base_w * 0.02)
        pos = (base_w - bubble_w - margin, base_h - bubble_h - margin)

        layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        layer.paste(bubble, pos, bubble)

        return Image.alpha_composite(base_image, layer)