from pathlib import Path
from PIL import Image, ImageDraw

folder = Path(__file__).resolve().parents[1] / 'assets'
folder.mkdir(exist_ok=True)
image = Image.new('RGBA', (256, 256))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((8, 8, 248, 248), radius=52, fill='#2563eb')
for y in (55, 109, 163):
    for x in (55, 109, 163):
        draw.rounded_rectangle((x, y, x + 38, y + 38), radius=6, fill='white')
draw.rounded_rectangle((77, 77, 177, 177), radius=20, fill='#102f74', outline='#93c5fd', width=7)
draw.polygon([(115, 103), (115, 154), (153, 128)], fill='white')
image.save(folder / 'atlastrim.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(folder / 'atlastrim.ico')
