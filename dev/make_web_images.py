"""공개 화면이 쓰는 그림의 가벼운 사본을 만든다. 원본을 바꾸거나 새 안내 그림을 넣었으면 다시 돌린다.

    pip install -r requirements-dev.txt   # Pillow
    python dev/make_web_images.py

만드는 것 (모두 stelline/static 아래, 원본은 그대로 둔다):
- og-image.jpg: 링크 미리보기 그림. og-image.png(190KB)를 JPEG 로 옮겨 17KB 남짓이 된다.
  미리보기 카드를 만드는 곳(디시인사이드·카카오톡·디스코드 등)이 모두 읽도록 WebP 가 아닌 일반(baseline) JPEG 로 둔다.
  og-image.png 는 지우지 않는다. 이미 만들어진 링크 카드가 그 주소를 기억해 계속 불러 간다.
- search/<원본 이름>.webp: 검색 안내 그림의 WebP 사본(예: 1.PNG → 1.PNG.webp).
  PNG 원본은 화면 갈무리라 손실 압축을 하면 글자 둘레가 번진다(PSNR 32dB 남짓). 그래서 무손실로 만든다.
  JPG 원본은 이미 손실 압축이라 품질 85 로 옮긴다(원본 대비 PSNR 41dB 이상, 눈으로는 같다).
  줄어드는 몫이 10%가 안 되면 만들지 않는다. 화면은 frontend/src/lib/webpCopies.js 에 적힌 것만 WebP 로 권한다.

결과마다 크기와 원본 대비 PSNR 을 찍는다. tests/test_static_images.py 가 사본이 원본과 맞는지 본다.
"""

import io
import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

STATIC = Path(__file__).resolve().parent.parent / "stelline" / "static"
JPEG_QUALITY = 85
WEBP_QUALITY = 85
# 이만큼도 줄지 않으면 사본을 두지 않는다. 파일만 늘고 얻는 것이 없다.
MIN_SAVING = 0.10


def psnr(reference, candidate):
    """두 그림이 얼마나 같은지(dB). 클수록 같고, 완전히 같으면 무한대다."""
    diff = ImageChops.difference(reference.convert("RGB"), candidate.convert("RGB"))
    mse = sum(rms * rms for rms in ImageStat.Stat(diff).rms) / 3
    return math.inf if mse == 0 else 10 * math.log10(255 * 255 / mse)


def opaque_rgb(image):
    """투명한 곳이 없으면 RGB 로 바꾼다. 쓰지 않는 알파 채널만큼 파일이 커진다."""
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        if rgba.getchannel("A").getextrema() != (255, 255):
            return rgba
    return image.convert("RGB")


def encode(image, fmt, **options):
    buffer = io.BytesIO()
    image.save(buffer, fmt, **options)
    return buffer.getvalue()


def write(path, data, original_path, reference):
    path.write_bytes(data)
    score = psnr(reference, Image.open(io.BytesIO(data)))
    before, after = original_path.stat().st_size, len(data)
    print(f"{path.relative_to(STATIC)}: {before // 1024}KB → {after // 1024}KB "
          f"({100 - after * 100 // before}% 감소, PSNR {score:.1f}dB)")


def make_og_image():
    original = STATIC / "og-image.png"
    image = opaque_rgb(Image.open(original))
    data = encode(image.convert("RGB"), "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=False)
    write(STATIC / "og-image.jpg", data, original, image)


def make_webp_copies():
    for original in sorted((STATIC / "search").iterdir()):
        if original.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        image = opaque_rgb(Image.open(original))
        if original.suffix.lower() == ".png":
            data = encode(image, "WEBP", lossless=True, method=6)
        else:
            data = encode(image, "WEBP", quality=WEBP_QUALITY, method=6)
        target = original.with_name(original.name + ".webp")
        if len(data) > original.stat().st_size * (1 - MIN_SAVING):
            print(f"{original.relative_to(STATIC)}: WebP 로 바꿔도 거의 줄지 않아 사본을 두지 않습니다.")
            target.unlink(missing_ok=True)
            continue
        write(target, data, original, image)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    make_og_image()
    make_webp_copies()
