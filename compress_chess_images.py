from PIL import Image
import os
import glob

img_dir = '/home/julianshen/projects/ebooksforme/chess-openings/EPUB/images'

# Compress board diagrams (PNG -> JPEG quality 80%)
board_files = glob.glob(os.path.join(img_dir, '*_*.png'))
for f in board_files:
    img = Image.open(f)
    # Resize if too large
    if max(img.size) > 1200:
        img.thumbnail((1200, 1200), Image.LANCZOS)
    base = os.path.splitext(f)[0]
    out = base + '.jpg'
    img = img.convert('RGB')
    img.save(out, 'JPEG', quality=80, optimize=True)
    os.remove(f)
    print(f"Compressed {os.path.basename(f)} -> {os.path.basename(out)}")

# Resize manga images if too large
manga_files = glob.glob(os.path.join(img_dir, 'manga-*.jpg'))
for f in manga_files:
    img = Image.open(f)
    if max(img.size) > 1200:
        img.thumbnail((1200, 1200), Image.LANCZOS)
        img.save(f, 'JPEG', quality=80, optimize=True)
        print(f"Resized {os.path.basename(f)}")

# Resize cover if too large
cover = os.path.join(img_dir, 'cover.png')
if os.path.exists(cover):
    img = Image.open(cover)
    if max(img.size) > 1200:
        img.thumbnail((1200, 1200), Image.LANCZOS)
    img = img.convert('RGB')
    img.save(cover.replace('.png', '.jpg'), 'JPEG', quality=85, optimize=True)
    os.remove(cover)
    print("Compressed cover.png -> cover.jpg")

print("Done!")
