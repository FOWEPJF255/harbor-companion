"""Render original lighthouse geometry, without external images or user photos."""
from pathlib import Path
import math
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "web" / "public" / "icons"


def render(size: int) -> Image.Image:
    scale = 4
    image = Image.new("RGB", (512 * scale, 512 * scale), "#111c2d")
    draw = ImageDraw.Draw(image)

    def box(values):
        return tuple(round(value * scale) for value in values)

    # All meaningful geometry is inside the central maskable safe circle.
    draw.ellipse(box((329, 106, 395, 172)), fill="#f4c9a8")
    draw.polygon([box(p) for p in [(198, 158), (268, 158), (286, 340), (180, 340)]], fill="#8dcfc0")
    draw.rounded_rectangle(box((194, 202, 272, 239)), radius=10 * scale, fill="#111c2d")
    draw.polygon([box(p) for p in [(189, 161), (277, 161), (258, 132), (208, 132)]], fill="#f4c9a8")
    for y in (346, 386):
        # Smooth waves formed from an original sampled quadratic curve.
        points = []
        for x in range(126, 387):
            points.append((x * scale, round((y - 14 * math.sin((x - 126) / 260 * math.pi * 2)) * scale)))
        draw.line(points, fill="#8dcfc0", width=16 * scale)
    return image.resize((size, size), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    DEST.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        render(size).save(DEST / f"harbor-{size}.png", optimize=True)
    render(512).save(DEST / "harbor-maskable-512.png", optimize=True)
    native = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res"
    if native.exists():
        for path in native.glob("mipmap-*/ic_launcher*.png"):
            with Image.open(path) as existing:
                size = existing.width
            if "foreground" in path.stem:
                adaptive = Image.new("RGB", (size, size), "#111c2d")
                inner = round(size * 0.75)
                adaptive.paste(render(inner), ((size - inner) // 2, (size - inner) // 2))
                adaptive.save(path, optimize=True)
            else:
                render(size).save(path, optimize=True)
        for path in native.glob("drawable*/splash.png"):
            with Image.open(path) as existing:
                width, height = existing.size
            splash = Image.new("RGB", (width, height), "#111c2d")
            size = max(48, min(width, height) // 5)
            splash.paste(render(size), ((width - size) // 2, (height - size) // 2))
            splash.save(path, optimize=True)
