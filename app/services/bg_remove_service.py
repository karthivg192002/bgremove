from rembg import remove
from PIL import Image, ImageFilter
import uuid
import os

from app.core.config import OUTPUT_DIR, WATERMARK_LOGO


class BackgroundRemoveService:

    @staticmethod
    def remove_background_and_add_watermark(input_path: str) -> str:

        output_filename = f"{uuid.uuid4().hex}.png"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        with Image.open(input_path) as img:
            img = img.convert("RGBA")

            result = remove(
                img,
                alpha_matting=True,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10
            )

        result = result.filter(
            ImageFilter.UnsharpMask(
                radius=1.2,
                percent=120,
                threshold=3
            )
        )

        if os.path.exists(WATERMARK_LOGO):
            result = BackgroundRemoveService._add_watermark(
                result,
                WATERMARK_LOGO
            )

        result.save(
            output_path,
            format="PNG",
            compress_level=0
        )

        return output_path

    @staticmethod
    def _add_watermark(base_image: Image.Image, logo_path: str) -> Image.Image:

        watermark = Image.open(logo_path).convert("RGBA")

        base_width, base_height = base_image.size

        # watermark width = 15% of main image
        target_width = int(base_width * 0.15)
        ratio = target_width / watermark.width
        target_height = int(watermark.height * ratio)

        watermark = watermark.resize(
            (target_width, target_height),
            Image.LANCZOS
        )

        margin = int(base_width * 0.02)

        position = (
            base_width - watermark.width - margin,
            base_height - watermark.height - margin
        )

        layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        layer.paste(watermark, position, watermark)

        return Image.alpha_composite(base_image, layer)