"""공개 화면이 쓰는 그림의 가벼운 사본(og-image.jpg, 검색 안내 그림의 WebP)이 원본과 맞는지 본다. DB 불필요.

사본은 dev/make_web_images.py 로 만든다. 원본만 바꾸고 사본을 다시 만들지 않으면, WebP 를 읽는
브라우저(지금은 사실상 전부)에는 옛 그림이 보인다. 그 사고를 여기서 잡는다.
"""

import math
import pathlib
import re

import pytest
from PIL import Image, ImageChops, ImageStat

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
STATIC_ROOT = PROJECT_ROOT / "stelline" / "static"
WEBP_LIST = PROJECT_ROOT / "frontend" / "src" / "lib" / "webpCopies.js"

# 같은 그림을 다시 압축한 것이면 40dB 를 넘는다(무손실은 무한대). 다른 그림이면 20dB 안팎이다.
SAME_PICTURE_DB = 35


def psnr(reference, candidate):
    diff = ImageChops.difference(reference.convert("RGB"), candidate.convert("RGB"))
    mse = sum(rms * rms for rms in ImageStat.Stat(diff).rms) / 3
    return math.inf if mse == 0 else 10 * math.log10(255 * 255 / mse)


def listed_originals():
    text = WEBP_LIST.read_text(encoding="utf-8")
    body = re.search(r"(?s)new Set\(\[(.*?)\]\)", text).group(1)
    return re.findall(r'"(/[^"]+)"', body)


def test_webp_list_is_not_empty():
    assert listed_originals()


@pytest.mark.parametrize("src", listed_originals())
def test_each_webp_copy_is_the_current_original_and_smaller(src):
    original = STATIC_ROOT / src.lstrip("/")
    copy = original.with_name(original.name + ".webp")
    assert original.is_file(), f"원본이 없습니다: {src}"
    assert copy.is_file(), f"WebP 사본이 없습니다. python dev/make_web_images.py 를 돌리세요: {src}.webp"
    with Image.open(original) as before, Image.open(copy) as after:
        assert after.format == "WEBP"
        assert after.size == before.size
        assert psnr(before, after) >= SAME_PICTURE_DB, (
            f"{src}.webp 가 지금 원본과 다른 그림입니다. 원본을 바꿨으면 사본도 다시 만드세요."
        )
    assert copy.stat().st_size < original.stat().st_size


def test_every_webp_copy_is_offered_by_the_page():
    """목록에 없는 사본은 화면이 쓰지 않는다. 목록에만 있고 파일이 없으면 그림이 깨진다(위 테스트)."""
    listed = {src.lstrip("/") + ".webp" for src in listed_originals()}
    on_disk = {path.relative_to(STATIC_ROOT).as_posix() for path in STATIC_ROOT.rglob("*.webp")}
    assert on_disk == listed


def test_link_preview_uses_the_light_jpeg_and_keeps_the_old_png():
    """og:image 는 17KB 남짓한 JPEG 로 알린다. og-image.png 는 남겨 둔다.

    이미 만들어진 링크 카드(예: 디시인사이드 글)가 그 주소를 기억해 계속 불러 간다.
    지우면 그 카드의 그림이 깨진다.
    """
    png = STATIC_ROOT / "og-image.png"
    jpg = STATIC_ROOT / "og-image.jpg"
    assert png.is_file()
    with Image.open(png) as before, Image.open(jpg) as after:
        assert after.format == "JPEG"
        assert after.size == before.size == (1200, 630)
        assert psnr(before, after) >= SAME_PICTURE_DB
    assert jpg.stat().st_size < png.stat().st_size // 5

    for html in (PROJECT_ROOT / "frontend" / "index.html", STATIC_ROOT / "index.html"):
        text = html.read_text(encoding="utf-8")
        assert '<meta property="og:image" content="/og-image.jpg">' in text, html
