from PIL import Image
from pathlib import Path

source = Path("public/curamind-logo.before-lavender.jpeg")
target = Path("public/curamind-logo.jpeg")

if not source.exists():
    raise SystemExit("Logo backup not found. Keeping the current logo unchanged.")

im = Image.open(source).convert("RGB")
hsv = im.convert("HSV")
out = []

for h, s, v in hsv.getdata():
    # Recolour green/teal hues to plum-purple, preserving brightness.
    if 45 <= h <= 155 and s >= 35:
        h = 190
    out.append((h, s, v))

hsv.putdata(out)
hsv.convert("RGB").save(target, "JPEG", quality=95, subsampling=0)
print("Logo recoloured from the original backup.")
