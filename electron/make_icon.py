"""
Draws the MHCI Assistant app icon and builds AppIcon.icns.

A warm near-black macOS tile (the app's dark canvas) with an off-white mark
that reads as both a sound wave and a raised hand: four finger bars plus an
angled thumb, i.e. voice + gesture.

Run from the project root (needs Pillow, which is in the project venv):
    .venv/bin/python electron/make_icon.py
Writes electron/icon_1024.png, electron/AppIcon.iconset/ and electron/AppIcon.icns,
then rebuild the app (cd electron && npm run build).
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent

S = 4                       # supersampling for smooth edges
N = 1024 * S
def s(v): return int(round(v * S))

def vgradient(w, h, top, bottom):
    g = Image.new("RGBA", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    return g.resize((w, h))

def rounded_mask(size, box, r):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=r, fill=255)
    return m

canvas = Image.new("RGBA", (N, N), (0, 0, 0, 0))

# macOS tile: 824px body centred on the 1024 grid, with the standard soft shadow
body = (s(100), s(100), s(924), s(924))
R = s(186)
shadow = Image.new("RGBA", (N, N), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle((body[0], body[1] + s(12), body[2], body[3] + s(12)), radius=R, fill=(0, 0, 0, 110))
canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s(18))))

tile = vgradient(N, N, (0x2b, 0x29, 0x22), (0x12, 0x11, 0x0a))
canvas.paste(tile, (0, 0), rounded_mask((N, N), body, R))

# hairline edge + a faint top highlight, like the app's cards
edge = Image.new("RGBA", (N, N), (0, 0, 0, 0))
d = ImageDraw.Draw(edge)
d.rounded_rectangle(body, radius=R, outline=(255, 255, 255, 26), width=s(3))
canvas.alpha_composite(edge)

# The mark
INK_TOP, INK_BOTTOM = (0xf7, 0xf6, 0xf2), (0xc9, 0xc7, 0xbe)
W = 66                       # bar width
BASE = 706                   # palm line (bottoms of the finger bars)
fingers = [                  # (centre x, top y): index, middle, ring, little
    (452, 352), (546, 304), (640, 346), (734, 432),
]

def bar_layer(x0, y0, x1, y1):
    """An off-white pill with a soft top-to-bottom shade, on its own layer."""
    layer = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    grad = vgradient(N, N, INK_TOP, INK_BOTTOM)
    mask = rounded_mask((N, N), (s(x0), s(y0), s(x1), s(y1)), s(W / 2))
    layer.paste(grad, (0, 0), mask)
    return layer

for cx, top in fingers:
    canvas.alpha_composite(bar_layer(cx - W / 2, top, cx + W / 2, BASE))

# Thumb: a shorter bar leaning out to the left
thumb = bar_layer(512 - W / 2, 512 - 104, 512 + W / 2, 512 + 104)
thumb = thumb.rotate(34, resample=Image.BICUBIC, center=(s(512), s(512)))
dx, dy = s(338 - 512), s(600 - 512)    # move its centre into place
canvas.alpha_composite(thumb.transform(thumb.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BICUBIC))

icon = canvas.resize((1024, 1024), Image.LANCZOS)
icon.save(HERE / "icon_1024.png")

# macOS icon set: every size at 1x and 2x, then pack it into AppIcon.icns
iconset = HERE / "AppIcon.iconset"
iconset.mkdir(exist_ok=True)
for size in (16, 32, 128, 256, 512):
    icon.resize((size, size), Image.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
    icon.resize((size * 2, size * 2), Image.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")
subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "AppIcon.icns")], check=True)
print("Wrote icon_1024.png, AppIcon.iconset/ and AppIcon.icns in", HERE)
