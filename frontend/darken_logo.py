from PIL import Image
from pathlib import Path

logo = Path("public/curamind-logo.jpeg")
backup = Path("public/curamind-logo.before-darker.jpeg")

if not logo.exists():
    raise SystemExit("Logo file not found.")

if not backup.exists():
    import shutil
    shutil.copy2(logo, backup)

image = Image.open(logo).convert("RGB")
hsv = image.convert("HSV")
pixels = []

for h, s, v in hsv.getdata():
    # Darken coloured logo areas by 12%, preserving pale backgrounds.
    if s >= 35:
        v = int(v * 0.88)
    pixels.append((h, s, v))

hsv.putdata(pixels)
hsv.convert("RGB").save(logo, "JPEG", quality=98, subsampling=0)

print("Done! Logo colours are now slightly darker.")
print("Original version saved as:", backup)
