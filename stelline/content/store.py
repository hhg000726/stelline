"""사이트 문구·그림의 저장과 조회.

원칙 하나만 지킨다. **화면은 어떤 경우에도 무너지지 않는다.**

- DB에 값이 없으면 registry의 기본값을 쓴다(지금 HTML에 적혀 있는 그 값이다).
- DB 조회가 통째로 실패해도 기본값으로 답한다. 예외를 밖으로 내보내지 않는다.
- 관리자가 일부러 비운 항목만 cleared로 표시되어 화면에서 자리째 사라진다.

값 검증은 저장할 때 한 번만 한다. 저장된 값은 이미 상한을 지킨 값이므로
읽는 쪽에서 다시 자를 필요가 없다.
"""

import logging

from stelline.content.images import ImageError, detect_image
from stelline.content.registry import CONTENT_ITEMS, IMAGE, TEXT, get_item
from stelline.database.connection import database_cursor

# 여러 줄 항목의 줄 수 상한. 글자 수만 막으면 줄바꿈만 잔뜩 넣어 세로로 늘일 수 있다.
MAX_LINES = 12

# 그림은 DB에 넣는다. 컨테이너를 다시 올리면 사라지는 파일 시스템과 달리
# 운영 DB는 백업 대상이라, 배포 때마다 그림이 날아가는 일이 없다.
META_COLUMNS = "content_key, cleared, text_value, image_mime, image_width, image_height, updated_at"

# 저장할 때 함께 덮어쓰는 열. 한 항목은 문구이거나 그림이므로 쓰지 않는 쪽은 NULL이 된다.
VALUE_COLUMNS = ("cleared", "text_value", "image_data", "image_mime", "image_width", "image_height")


class ContentError(ValueError):
    """관리자에게 그대로 보여 줄 수 있는 저장 오류."""


def _clean_line(line):
    """탭·제어문자를 공백으로 바꾼다. 붙여넣기로 딸려 오는 보이지 않는 문자를 막는다."""
    return "".join(" " if character < " " else character for character in line).strip()


def normalize_text(item, raw):
    """저장 전에 문구를 다듬고 상한을 확인한다. 어기면 ContentError."""
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [_clean_line(line) for line in text.split("\n")]
    if item.get("multiline"):
        # 빈 줄은 버린다. 남겨 두면 화면에 빈 칸만 늘어난다.
        lines = [line for line in lines if line]
        if len(lines) > MAX_LINES:
            raise ContentError(f"줄이 너무 많습니다. {MAX_LINES}줄까지 넣을 수 있습니다.")
        value = "\n".join(lines)
    else:
        # 한 줄짜리 항목에 줄바꿈이 들어오면 공백으로 이어 붙인다.
        value = " ".join(line for line in lines if line)

    limit = item["max_length"]
    if len(value) > limit:
        raise ContentError(f"글자 수가 상한을 넘었습니다. {limit}자까지 넣을 수 있습니다(지금 {len(value)}자).")
    return value


def validate_image(item, data):
    """(MIME, 너비, 높이)를 돌려주고, 규격을 벗어나면 ContentError."""
    if len(data) > item["max_bytes"]:
        raise ContentError(
            f"파일이 너무 큽니다. {item['max_bytes'] // 1000}KB까지 올릴 수 있습니다"
            f"(지금 {len(data) // 1000}KB)."
        )
    try:
        _, mime, width, height = detect_image(data)
    except ImageError as error:
        raise ContentError(str(error)) from error

    size = f"{width}x{height}"
    if width < item["min_width"] or height < item["min_height"]:
        raise ContentError(
            f"그림이 너무 작습니다. 최소 {item['min_width']}x{item['min_height']} 이상이어야 합니다(지금 {size})."
        )
    if width > item["max_width"] or height > item["max_height"]:
        raise ContentError(
            f"그림이 너무 큽니다. 최대 {item['max_width']}x{item['max_height']}까지 올릴 수 있습니다(지금 {size})."
        )
    aspect = width / height
    if not item["min_aspect"] <= aspect <= item["max_aspect"]:
        raise ContentError(
            f"가로세로 비율이 맞지 않습니다(지금 {aspect:.2f}). "
            f"{item['min_aspect']:.2f}~{item['max_aspect']:.2f} 사이여야 합니다. {item['aspect_hint']}"
        )
    return mime, width, height


def _cache_tag(updated_at):
    """그림 주소에 붙일 짧은 값. 바뀐 그림이 곧바로 보이게 한다."""
    try:
        return str(int(updated_at.timestamp()))
    except (AttributeError, OSError, ValueError):
        return "0"


def load_overrides():
    """DB에 저장된 변경분만 읽는다(그림 원본은 빼고 메타데이터만)."""
    with database_cursor() as cursor:
        cursor.execute("SELECT " + META_COLUMNS + " FROM site_contents")
        return {row["content_key"]: row for row in cursor.fetchall()}


def _from_default(item):
    """코드에 적어 둔 기본값으로 답한다. 기본값이 비면 그 자리는 화면에서 사라진다."""
    value = item.get("default") or ""
    return {"type": item["type"], "value": value, "hidden": not value, "source": "default"}


def _resolve(key, item, override):
    """항목 하나의 최종 표시값을 정한다."""
    if override is None:
        # 아직 손대지 않은 항목. HTML에 적힌 값과 같은 기본값을 쓴다.
        return _from_default(item)
    if override["cleared"]:
        return {"type": item["type"], "value": "", "hidden": True, "source": "cleared"}

    if item["type"] == IMAGE:
        if not override["image_mime"]:
            # 그림이 없는데 비움 표시도 없다면 데이터가 어긋난 것이다. 기본값으로 돌아간다.
            return _from_default(item)
        return {
            "type": IMAGE,
            "value": f"/api/content/image/{key}?v={_cache_tag(override['updated_at'])}",
            "hidden": False,
            "source": "custom",
            "width": override["image_width"],
            "height": override["image_height"],
        }

    value = override["text_value"] or ""
    if not value:
        # 빈 문자열이 비움 표시 없이 남아 있으면 기본값으로 되돌린다(빈 화면 방지).
        return _from_default(item)
    return {"type": TEXT, "value": value, "hidden": False, "source": "custom"}


def resolve_items():
    """모든 항목의 표시값. 어떤 이유로 실패해도 기본값을 돌려주고 예외를 내지 않는다."""
    try:
        overrides = load_overrides()
    except Exception:
        logging.exception("사이트 콘텐츠 불러오기 실패 - 기본값으로 표시합니다")
        overrides = {}
    return {key: _resolve(key, item, overrides.get(key)) for key, item in CONTENT_ITEMS.items()}


def admin_rows():
    """관리자 화면용. 항목 정의와 지금 값, 어디서 온 값인지를 함께 준다."""
    try:
        overrides = load_overrides()
    except Exception:
        logging.exception("관리자 사이트 콘텐츠 불러오기 실패")
        overrides = {}
    rows = {}
    for key, item in CONTENT_ITEMS.items():
        override = overrides.get(key)
        resolved = _resolve(key, item, override)
        # 문구 양식에 채워 넣을 원본. 비움 상태면 빈 칸으로 두어 지금 상태가 그대로 보인다.
        editing = "" if resolved["hidden"] or item["type"] != TEXT else resolved["value"]
        rows[key] = {**resolved, "editing_text": editing, "updated_at": override["updated_at"] if override else None}
    return rows


def load_image(key):
    """그림 원본과 MIME을 돌려준다. 없으면 None."""
    item = get_item(key)
    if item is None or item["type"] != IMAGE:
        return None
    with database_cursor() as cursor:
        cursor.execute(
            "SELECT image_data, image_mime, updated_at FROM site_contents"
            " WHERE content_key = %s AND cleared = 0 AND image_data IS NOT NULL",
            (key,),
        )
        return cursor.fetchone()


def _upsert(key, **values):
    """한 항목의 값을 통째로 덮어쓴다. 쓰지 않은 열은 NULL이 되어 이전 값이 남지 않는다."""
    payload = [values.get(column) for column in VALUE_COLUMNS]
    assignments = ", ".join(f"{column} = VALUES({column})" for column in VALUE_COLUMNS)
    placeholders = ", ".join(["%s"] * len(VALUE_COLUMNS))
    with database_cursor() as cursor:
        cursor.execute(
            "INSERT INTO site_contents (content_key, " + ", ".join(VALUE_COLUMNS) + ")"
            " VALUES (%s, " + placeholders + ")"
            " ON DUPLICATE KEY UPDATE " + assignments + ", updated_at = CURRENT_TIMESTAMP",
            [key, *payload],
        )


def save_text(key, raw):
    """문구를 저장한다. 빈 값은 비움이라 화면에서 자리째 사라진다."""
    item = get_item(key)
    if item is None or item["type"] != TEXT:
        raise ContentError("수정할 수 없는 항목입니다.")
    value = normalize_text(item, raw)
    if not value:
        clear_item(key)
        return ""
    _upsert(key, cleared=0, text_value=value)
    return value


def save_image(key, data):
    """그림을 저장한다. 형식·용량·크기·비율을 모두 통과해야 들어간다."""
    item = get_item(key)
    if item is None or item["type"] != IMAGE:
        raise ContentError("수정할 수 없는 항목입니다.")
    if not data:
        raise ContentError("올릴 파일을 고르세요.")
    mime, width, height = validate_image(item, data)
    _upsert(key, cleared=0, image_data=data, image_mime=mime, image_width=width, image_height=height)
    return mime, width, height


def clear_item(key):
    """항목을 비운다. 화면에서 그 자리가 통째로 사라진다."""
    if get_item(key) is None:
        raise ContentError("수정할 수 없는 항목입니다.")
    _upsert(key, cleared=1)


def reset_item(key):
    """기본값으로 되돌린다(저장된 변경분을 지운다)."""
    if get_item(key) is None:
        raise ContentError("수정할 수 없는 항목입니다.")
    with database_cursor() as cursor:
        cursor.execute("DELETE FROM site_contents WHERE content_key = %s", (key,))
