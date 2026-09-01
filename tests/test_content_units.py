"""사이트 문구·그림 기능의 DB 없는 검증.

여기서 지키려는 것은 하나다. **어떤 값이 들어와도 공개 화면이 무너지지 않는다.**
그래서 값 검증(글자 수·그림 규격)과 값이 없을 때의 되돌아가기(fallback), 그리고
화면 HTML과 항목 목록이 서로 맞는지를 본다.
"""

import pathlib
import re
import struct
import zlib

import pytest

from stelline.content import registry
from stelline.content.images import ImageError, detect_image
from stelline.content.registry import CONTENT_GROUPS, CONTENT_ITEMS, IMAGE, TEXT
from stelline.content.store import ContentError, _resolve, normalize_text, validate_image

STATIC_ROOT = pathlib.Path(__file__).resolve().parent.parent / "stelline" / "static"
PAGE_FILES = [
    STATIC_ROOT / "index.html",
    STATIC_ROOT / "search" / "index.html",
    STATIC_ROOT / "karaoke" / "index.html",
    STATIC_ROOT / "congratulation" / "index.html",
    STATIC_ROOT / "offline" / "index.html",
]


def make_png(width, height):
    """검증에 쓸 최소 크기의 진짜 PNG를 만든다(Pillow 없이)."""
    def chunk(kind, payload):
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x00\x00\x00" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------- 항목 목록

def test_every_item_has_the_limits_its_type_needs():
    """상한이 빠진 항목이 하나라도 있으면 검증이 통째로 비어 버린다."""
    for key, item in CONTENT_ITEMS.items():
        assert item["title"] and item["description"], key
        if item["type"] == TEXT:
            assert item["max_length"] > 0, key
            assert isinstance(item["default"], str), key
        else:
            for rule in ("max_bytes", "min_width", "min_height", "max_width", "max_height", "min_aspect", "max_aspect"):
                assert item[rule], f"{key}: {rule}"


def test_default_text_fits_its_own_limit():
    """기본값이 상한을 넘으면, 아무것도 고치지 않은 상태에서 이미 규칙을 어기는 셈이다."""
    for key, item in CONTENT_ITEMS.items():
        if item["type"] == TEXT:
            assert len(item["default"]) <= item["max_length"], key


def test_groups_cover_every_item_exactly_once():
    listed = [item["key"] for group in CONTENT_GROUPS for item in group["items"]]
    assert sorted(listed) == sorted(CONTENT_ITEMS)


# ---------------------------------------------------------------- 화면 HTML과의 짝

def content_keys_in_pages():
    keys = set()
    for path in PAGE_FILES:
        keys.update(re.findall(r'data-content-key="([^"]+)"', path.read_text(encoding="utf-8")))
    return keys


def test_pages_only_reference_registered_keys():
    """HTML에만 있는 키는 영원히 값이 채워지지 않는다(관리자 화면에 나오지 않으므로)."""
    assert content_keys_in_pages() <= set(CONTENT_ITEMS)


def test_every_registered_item_is_used_by_a_page():
    """관리자가 고칠 수는 있는데 화면에는 반영되지 않는 항목을 만들지 않는다."""
    assert set(CONTENT_ITEMS) <= content_keys_in_pages()


def test_pages_load_the_content_script():
    for path in PAGE_FILES:
        assert "/assets/content.js" in path.read_text(encoding="utf-8"), path


def test_empty_by_default_items_start_hidden_in_html():
    """기본값이 빈 항목은 HTML에서 이미 hidden 이어야 한다.

    그렇지 않으면 값을 받아오기 전 잠깐 빈 칸이 보였다가 사라진다.
    """
    pages = "\n".join(path.read_text(encoding="utf-8") for path in PAGE_FILES)
    for key, item in CONTENT_ITEMS.items():
        if item["type"] == TEXT and item["default"]:
            continue
        if item["type"] == IMAGE and item["default"]:
            continue
        marker = re.search(r'[^\n<]*data-content-key="' + key + r'"[^\n>]*', pages)
        assert marker and "hidden" in marker.group(0), key


# ---------------------------------------------------------------- 문구 검증

def text_item(max_length=20, multiline=False):
    return {"type": TEXT, "max_length": max_length, "multiline": multiline, "default": "기본"}


def test_text_over_the_limit_is_refused():
    with pytest.raises(ContentError):
        normalize_text(text_item(max_length=5), "여섯 글자가 넘는 문구")


def test_text_at_the_limit_is_kept():
    assert normalize_text(text_item(max_length=5), "다섯글자다") == "다섯글자다"


def test_single_line_item_flattens_pasted_newlines():
    """한 줄짜리 칸에 여러 줄을 붙여 넣어도 줄이 늘어나지 않는다."""
    assert normalize_text(text_item(), "첫 줄\n둘째 줄") == "첫 줄 둘째 줄"


def test_multiline_item_drops_blank_lines():
    assert normalize_text(text_item(multiline=True), "가\n\n\n나\n") == "가\n나"


def test_multiline_item_refuses_too_many_lines():
    """줄바꿈만 잔뜩 넣어 세로로 늘이는 것을 막는다."""
    with pytest.raises(ContentError):
        normalize_text(text_item(max_length=200, multiline=True), "\n".join("줄" for _ in range(20)))


def test_control_characters_are_replaced_with_spaces():
    assert normalize_text(text_item(), "가\t나\x07다") == "가 나 다"


def test_blank_text_normalizes_to_empty():
    """빈 값은 오류가 아니라 '비움'이다. 저장하면 화면에서 그 자리가 사라진다."""
    assert normalize_text(text_item(), "   \n  ") == ""


# ---------------------------------------------------------------- 그림 검증

def image_item(**overrides):
    item = {
        "type": IMAGE, "max_bytes": 200_000,
        "min_width": 100, "min_height": 50, "max_width": 1000, "max_height": 800,
        "min_aspect": 1.0, "max_aspect": 3.0, "aspect_hint": "16:9 안팎",
    }
    item.update(overrides)
    return item


def test_png_dimensions_are_read_from_the_file_itself():
    assert detect_image(make_png(120, 60))[1:] == ("image/png", 120, 60)


def test_files_that_are_not_images_are_refused():
    """확장자가 아니라 파일 앞머리를 본다. 이름만 .png 인 스크립트는 통과하지 못한다."""
    with pytest.raises(ImageError):
        detect_image(b"<svg xmlns='http://www.w3.org/2000/svg'><script>1</script></svg>")


def test_empty_upload_is_refused():
    with pytest.raises(ImageError):
        detect_image(b"")


def test_image_within_the_rules_is_accepted():
    assert validate_image(image_item(), make_png(200, 100))[0] == "image/png"


def test_image_that_is_too_small_is_refused():
    with pytest.raises(ContentError):
        validate_image(image_item(), make_png(80, 40))


def test_image_that_is_too_large_is_refused():
    with pytest.raises(ContentError):
        validate_image(image_item(), make_png(1200, 500))


def test_image_with_the_wrong_aspect_is_refused():
    """비율이 어긋난 그림은 잘리거나 칸을 밀어내므로 아예 받지 않는다."""
    with pytest.raises(ContentError):
        validate_image(image_item(), make_png(120, 200))


def test_image_over_the_size_limit_is_refused():
    with pytest.raises(ContentError):
        validate_image(image_item(max_bytes=100), make_png(200, 100))


# ---------------------------------------------------------------- 값이 없을 때

def test_missing_row_falls_back_to_the_default():
    item = CONTENT_ITEMS["main_hero_subtitle"]
    resolved = _resolve("main_hero_subtitle", item, None)
    assert resolved == {"type": TEXT, "value": item["default"], "hidden": False, "source": "default"}


def test_cleared_row_hides_the_spot():
    override = {"cleared": 1, "text_value": None, "image_mime": None,
                "image_width": None, "image_height": None, "updated_at": None}
    resolved = _resolve("main_hero_subtitle", CONTENT_ITEMS["main_hero_subtitle"], override)
    assert resolved["hidden"] is True


def test_row_with_an_empty_value_falls_back_instead_of_blanking():
    """비움 표시 없이 값만 빈 행은 데이터가 어긋난 것이다. 빈 화면 대신 기본값으로 돌아간다."""
    override = {"cleared": 0, "text_value": "", "image_mime": None,
                "image_width": None, "image_height": None, "updated_at": None}
    resolved = _resolve("main_hero_subtitle", CONTENT_ITEMS["main_hero_subtitle"], override)
    assert resolved["value"] == CONTENT_ITEMS["main_hero_subtitle"]["default"]
    assert resolved["hidden"] is False


def test_image_row_without_data_falls_back_to_the_default_picture():
    override = {"cleared": 0, "text_value": None, "image_mime": None,
                "image_width": None, "image_height": None, "updated_at": None}
    resolved = _resolve("search_step_pc_1_image", CONTENT_ITEMS["search_step_pc_1_image"], override)
    assert resolved["value"] == "/search/1.PNG"


def test_api_answers_with_defaults_when_the_database_is_unreachable(client, monkeypatch):
    """DB가 죽어도 화면은 지금 모습 그대로 보여야 한다."""
    def explode():
        raise RuntimeError("DB 연결 실패")

    monkeypatch.setattr("stelline.content.store.load_overrides", explode)
    payload = client.get("/api/content").get_json()
    assert payload["main_hero_subtitle"]["value"] == CONTENT_ITEMS["main_hero_subtitle"]["default"]
    assert len(payload) == len(CONTENT_ITEMS)


def test_preview_style_is_set_for_every_item():
    """관리자 미리보기가 실제 화면과 같은 크기로 보이려면 항목마다 자리가 정해져 있어야 한다."""
    assert all(item["preview"] for item in registry.CONTENT_ITEMS.values())
