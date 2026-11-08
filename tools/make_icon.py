"""Gera assets/icon.ico: anel com ponto, na cor de destaque, sobre quadrado escuro arredondado."""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=56, fill=(11, 13, 18, 255), outline=(37, 43, 56, 255),
                    width=6)
accent = (61, 245, 167, 255)
c = SIZE / 2
d.ellipse([c - 78, c - 78, c + 78, c + 78], outline=accent, width=18)
d.ellipse([c - 20, c - 20, c + 20, c + 20], fill=accent)
for x0, y0, x1, y1 in ((c - 9, 22, c + 9, 64), (c - 9, SIZE - 64, c + 9, SIZE - 22),
                       (22, c - 9, 64, c + 9), (SIZE - 64, c - 9, SIZE - 22, c + 9)):
    d.rectangle([x0, y0, x1, y1], fill=accent)

out = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
out.parent.mkdir(exist_ok=True)
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(out)
