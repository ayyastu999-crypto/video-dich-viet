"""Remove background from images using rembg (local).

Inspired by RevidAPI remove_background:
- Multiple AI models: u2net, u2net_human_seg, isnet-general-use
- PNG output with transparency
- Useful for creating logo overlays, thumbnails
"""
from pathlib import Path

from src.steps.base import BaseStep


class RemoveBackground(BaseStep):
    def run(self, image_path: Path, model: str = None) -> dict:
        """Remove background from image.

        Args:
            image_path: Input image (PNG, JPG, WEBP)
            model: AI model - u2net (default), u2net_human_seg, isnet-general-use

        Returns:
            dict with 'output_path' to transparent PNG
        """
        from rembg import remove
        from PIL import Image

        if model is None:
            model = self.config.get("revid", {}).get("remove_bg_model", "u2net")

        output_dir = self.ensure_dir("output")
        out_path = output_dir / f"{image_path.stem}_nobg.png"

        self.log(f"Removing background: {image_path.name} (model={model})")

        img = Image.open(str(image_path))
        result = remove(img, session_name=model)
        result.save(str(out_path))

        self.log(f"Saved: {out_path.name}")
        return {"output_path": out_path}
