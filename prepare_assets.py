"""
prepare_assets.py
Copies brand assets (poster, logo, and the 3 dedicated product photos)
into static/images/ for "Cả 1 tổ phê" (Cà phê Tổ 1).
"""

import os
import shutil
from PIL import Image, ImageOps

ARTIFACT_DIR = r"C:/Users/Admin/.gemini/antigravity/brain/3956b360-b020-474c-a04c-2ebc5d3d9919"
UPLOAD_DIR = os.path.join(ARTIFACT_DIR, ".user_uploaded")

POSTER_SRC = os.path.join(ARTIFACT_DIR, "poster.jpg")
LOGO_SRC = os.path.join(ARTIFACT_DIR, "logo.png")

# Dedicated product images provided by the user:
# 1. Cà phê đen: media_1794409083501_9683539d.jpg
# 2. Cà phê sữa: media_1794409087870_384dbf7b.jpg
# 3. Bạc xỉu:    media_1794409184964_c08ab215.jpg
PRODUCT_SOURCES = {
    "ca_phe_den.jpg": os.path.join(UPLOAD_DIR, "media_1794409083501_9683539d.jpg"),
    "ca_phe_sua.jpg": os.path.join(UPLOAD_DIR, "media_1794409087870_384dbf7b.jpg"),
    "bac_xiu.jpg": os.path.join(UPLOAD_DIR, "media_1794409184964_c08ab215.jpg"),
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, "static", "images")


def prepare_brand_assets() -> None:
    os.makedirs(IMG_DIR, exist_ok=True)

    poster_dst = os.path.join(IMG_DIR, "poster.jpg")
    logo_dst = os.path.join(IMG_DIR, "logo.png")

    if os.path.exists(POSTER_SRC):
        shutil.copy2(POSTER_SRC, poster_dst)
    if os.path.exists(LOGO_SRC):
        shutil.copy2(LOGO_SRC, logo_dst)

    for filename, src_path in PRODUCT_SOURCES.items():
        if os.path.exists(src_path):
            img = Image.open(src_path).convert("RGB")
            # Create a clean 600x600 product thumbnail preserving full drink visibility
            thumb = ImageOps.fit(img, (600, 600), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            out_path = os.path.join(IMG_DIR, filename)
            thumb.save(out_path, quality=94)
            print(f"Saved product image: {out_path}")


if __name__ == "__main__":
    prepare_brand_assets()
