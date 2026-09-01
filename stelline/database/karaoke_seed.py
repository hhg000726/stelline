"""노래방 번호 데이터를 표 형식 텍스트(TSV/CSV)로 일괄 적재한다.

관리자 화면의 붙여넣기 폼과 CLI(`python -m stelline.database.karaoke_seed`)가
같은 파싱·검증 로직을 사용한다.
"""

import argparse
import csv
import logging
from datetime import date
from pathlib import Path

from stelline.database.connection import get_connection

SEED_PATH = Path(__file__).resolve().parent / "data" / "karaoke_seed.tsv"

# DB에 실제로 저장하는 열.
SONG_COLUMNS = ("title", "title_alt", "artist", "members", "section", "category", "tj", "ky", "release_date")

# 붙여넣기 편의를 위해 한글 머리글도 인식한다.
HEADER_ALIASES = {
    "title": "title", "곡명": "title", "제목": "title", "노래": "title",
    "title_alt": "title_alt", "원제": "title_alt", "원제목": "title_alt", "검색어": "title_alt",
    "artist": "artist", "가수": "artist", "아티스트": "artist",
    "members": "members", "멤버": "members", "참여멤버": "members",
    "section": "section", "구분": "section",
    "category": "category", "종류": "category", "분류": "category",
    "tj": "tj", "태진": "tj",
    "ky": "ky", "금영": "ky",
    "release_date": "release_date", "발매일": "release_date", "공개일": "release_date",
}

# 머리글 줄이 없을 때 가정하는 순서(참고 사이트 표와 같은 순서다).
DEFAULT_COLUMNS = ("title", "artist", "tj", "ky")

SECTIONS = {
    "group": "group", "단체": "group", "스텔라이브": "group",
    "unit": "unit", "유닛": "unit",
    "collab": "collab", "콜라보": "collab", "콜라보 곡": "collab",
    "gift": "gift", "기프트": "gift", "기프트 곡": "gift",
    "solo": "solo", "개인": "solo", "솔로": "solo", "멤버": "solo",
}
CATEGORIES = {
    "original": "original", "오리지널": "original", "오리지날": "original",
    "cover": "cover", "커버": "cover",
}

SECTION_LABELS = {"group": "단체", "unit": "유닛", "collab": "콜라보", "gift": "기프트", "solo": "개인"}
CATEGORY_LABELS = {"original": "오리지널", "cover": "커버"}

# 멤버 마스터. 공개 화면 필터 칩의 순서와 유닛 묶음을 결정한다.
#
# 유닛은 고정이 아니다. 2025-09-20 개편으로 미스틱이 사라지고 에버리스가 생겼으며,
# 아야츠노 유니는 미스틱에서 에버리스로 옮겼다.
#
# 데뷔일·졸업일은 곡의 참여 멤버가 맞는지 검증하는 기준으로만 쓰고 공개 화면에는 내보내지 않는다.
# (name, unit, former_units, debut_date, graduated_at, display_order)
MEMBER_SEED = (
    ("아이리 칸나", "MYSTIC", None, "2023-01-07", "2024-12-02", 1),
    ("아야츠노 유니", "EVERYS", "MYSTIC", "2023-01-08", None, 2),
    ("사키하네 후야", "EVERYS", None, "2025-09-20", None, 3),
    ("시라유키 히나", "UNIVERSE", None, "2023-06-10", None, 4),
    ("네네코 마시로", "UNIVERSE", None, "2023-06-11", None, 5),
    ("아카네 리제", "UNIVERSE", None, "2023-06-11", None, 6),
    ("아라하시 타비", "UNIVERSE", None, "2023-06-10", None, 7),
    ("텐코 시부키", "CLICHÉ", None, "2024-05-18", None, 8),
    ("아오쿠모 린", "CLICHÉ", None, "2024-05-19", None, 9),
    ("하나코 나나", "CLICHÉ", None, "2024-05-18", None, 10),
    ("유즈하 리코", "CLICHÉ", None, "2024-05-19", None, 11),
)
KNOWN_MEMBERS = {row[0] for row in MEMBER_SEED}

MAX_LENGTHS = {"title": 255, "title_alt": 255, "artist": 255, "members": 512, "tj": 16, "ky": 16}
EMPTY_MARKS = {"", "-", "–", "—", "없음", "x", "X"}


class SeedError(Exception):
    """행 단위 검증에 실패했음을 알린다. 메시지는 관리자 화면에 그대로 보여준다."""


def _split_line(line):
    """탭 우선, 없으면 쉼표로 나눈다. 표에서 복사하면 대개 탭으로 구분된다."""
    if "\t" in line:
        return [cell.strip() for cell in line.split("\t")]
    return [cell.strip() for cell in next(csv.reader([line]), [])]


def _resolve_header(cells):
    """머리글 줄이면 열 이름 목록을, 아니면 None을 돌려준다."""
    normalized = [HEADER_ALIASES.get(cell.strip().lower().replace(" ", "")) for cell in cells]
    if "title" in normalized and "artist" in normalized:
        return normalized
    return None


def _clean_number(value, field, line_no):
    value = (value or "").strip()
    if value in EMPTY_MARKS:
        return None
    if not value.isdigit():
        raise SeedError(f"{line_no}번째 줄: {field.upper()} 번호는 숫자만 입력하세요(현재 값: {value}).")
    if len(value) > MAX_LENGTHS[field]:
        raise SeedError(f"{line_no}번째 줄: {field.upper()} 번호가 너무 깁니다.")
    return value


def _clean_date(value, line_no):
    """YYYY-MM-DD 형식만 받는다. 비어 있으면 '모름'을 뜻하는 None이다."""
    value = (value or "").strip().replace(".", "-").replace("/", "-").rstrip("-")
    if not value:
        return None
    parts = value.split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise SeedError(f"{line_no}번째 줄: 발매일은 2026-05-08 형식으로 입력하세요(현재 값: {value}).")
    year, month, day = (int(part) for part in parts)
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        raise SeedError(f"{line_no}번째 줄: 발매일 '{value}'은(는) 없는 날짜입니다.") from None


def _clean_members(value, line_no, warnings):
    parts = [part.strip() for part in (value or "").replace("/", ",").split(",")]
    members, seen = [], set()
    for part in parts:
        if not part or part in seen:
            continue
        seen.add(part)
        if part not in KNOWN_MEMBERS:
            warnings.append(f"{line_no}번째 줄: '{part}'은(는) 등록된 멤버가 아닙니다. 그대로 저장합니다.")
        members.append(part)
    joined = ", ".join(members)
    if len(joined) > MAX_LENGTHS["members"]:
        raise SeedError(f"{line_no}번째 줄: 멤버 목록이 너무 깁니다.")
    return joined or None


def _resolve_choice(raw, table, line_no, default, label, allowed):
    """구분·종류처럼 정해진 값 중 하나여야 하는 열을 해석한다."""
    value = (raw or "").strip()
    if not value:
        return default
    resolved = table.get(value.lower()) or table.get(value)
    if resolved is None:
        raise SeedError(f"{line_no}번째 줄: {label} 값 '{value}'을(를) 알 수 없습니다. ({allowed})")
    return resolved


def parse_rows(text):
    """표 형식 텍스트를 DB에 넣을 수 있는 행 목록으로 바꾼다.

    반환값은 (행 목록, 경고 메시지 목록)이다. 형식 오류는 SeedError로 올린다.
    """
    lines = [line for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip()]
    if not lines:
        raise SeedError("입력한 내용이 없습니다.")

    columns = _resolve_header(_split_line(lines[0]))
    if columns is None:
        columns = list(DEFAULT_COLUMNS)
        body_start = 0
    else:
        body_start = 1
    if not lines[body_start:]:
        raise SeedError("머리글만 있고 데이터 줄이 없습니다.")

    rows, warnings = [], []
    for offset, line in enumerate(lines[body_start:]):
        line_no = body_start + offset + 1
        cells = _split_line(line)
        values = {}
        for index, column in enumerate(columns):
            if column and index < len(cells):
                values[column] = cells[index]

        title = (values.get("title") or "").strip()
        artist = (values.get("artist") or "").strip()
        if not title:
            raise SeedError(f"{line_no}번째 줄: 곡명이 비어 있습니다.")
        if not artist:
            raise SeedError(f"{line_no}번째 줄: 가수가 비어 있습니다.")
        for field in ("title", "artist"):
            if len(values.get(field, "")) > MAX_LENGTHS[field]:
                raise SeedError(f"{line_no}번째 줄: {field}이(가) 너무 깁니다({MAX_LENGTHS[field]}자 이내).")

        title_alt = (values.get("title_alt") or "").strip() or None
        if title_alt and len(title_alt) > MAX_LENGTHS["title_alt"]:
            raise SeedError(f"{line_no}번째 줄: title_alt이(가) 너무 깁니다({MAX_LENGTHS['title_alt']}자 이내).")

        rows.append({
            "title": title,
            "title_alt": title_alt,
            "artist": artist,
            "members": _clean_members(values.get("members"), line_no, warnings),
            "section": _resolve_choice(values.get("section"), SECTIONS, line_no, "solo", "구분", "단체/유닛/콜라보/기프트/개인"),
            "category": _resolve_choice(values.get("category"), CATEGORIES, line_no, "cover", "종류", "오리지널/커버"),
            "tj": _clean_number(values.get("tj"), "tj", line_no),
            "ky": _clean_number(values.get("ky"), "ky", line_no),
            "release_date": _clean_date(values.get("release_date"), line_no),
        })

    seen_keys = set()
    for row in rows:
        key = (row["title"], row["artist"])
        if key in seen_keys:
            warnings.append(f"'{row['title']} - {row['artist']}'이(가) 입력 안에서 중복됩니다. 마지막 값으로 저장됩니다.")
        seen_keys.add(key)
    return rows, warnings


def import_songs(rows, replace=False):
    """행 목록을 karaoke_songs에 적재한다. 같은 곡명+가수는 덮어쓴다."""
    if not rows:
        raise SeedError("저장할 곡이 없습니다.")

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            if replace:
                cursor.execute("DELETE FROM karaoke_songs")
                existing = set()
            else:
                cursor.execute("SELECT title, artist FROM karaoke_songs")
                existing = {(row["title"], row["artist"]) for row in cursor.fetchall()}

            inserted = updated = 0
            payload = []
            for row in rows:
                payload.append(tuple(row[column] for column in SONG_COLUMNS))
                if (row["title"], row["artist"]) in existing:
                    updated += 1
                else:
                    inserted += 1

            column_list = ", ".join("`" + column + "`" for column in SONG_COLUMNS)
            placeholders = ", ".join(["%s"] * len(SONG_COLUMNS))
            assignments = ", ".join(
                "`" + column + "` = VALUES(`" + column + "`)"
                for column in SONG_COLUMNS
                if column not in ("title", "artist")
            )
            cursor.executemany(
                f"INSERT INTO karaoke_songs ({column_list}) VALUES ({placeholders})"
                f" ON DUPLICATE KEY UPDATE {assignments}",
                payload,
            )
            cursor.executemany(
                "INSERT INTO karaoke_members (name, unit, former_units, debut_date, graduated_at, display_order)"
                " VALUES (%s, %s, %s, %s, %s, %s)"
                " ON DUPLICATE KEY UPDATE unit = VALUES(unit), former_units = VALUES(former_units),"
                " debut_date = VALUES(debut_date), graduated_at = VALUES(graduated_at),"
                " display_order = VALUES(display_order)",
                MEMBER_SEED,
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    logging.info("노래방 데이터 적재 완료: 추가=%s, 갱신=%s, 초기화=%s", inserted, updated, replace)
    return {"inserted": inserted, "updated": updated, "total": len(rows), "replaced": replace}


def import_text(text, replace=False):
    rows, warnings = parse_rows(text)
    stats = import_songs(rows, replace=replace)
    stats["warnings"] = warnings
    return stats


def load_seed_text():
    if not SEED_PATH.exists():
        raise SeedError(f"기본 데이터 파일을 찾을 수 없습니다: {SEED_PATH}")
    return SEED_PATH.read_text(encoding="utf-8")


def import_seed_file(replace=False):
    return import_text(load_seed_text(), replace=replace)


def main():
    parser = argparse.ArgumentParser(description="노래방 번호 기본 데이터를 DB에 적재합니다.")
    parser.add_argument("path", nargs="?", help="TSV/CSV 파일 경로. 생략하면 기본 시드 파일을 사용합니다.")
    parser.add_argument("--replace", action="store_true", help="기존 노래방 곡을 모두 지우고 새로 넣습니다.")
    args = parser.parse_args()

    text = Path(args.path).read_text(encoding="utf-8") if args.path else load_seed_text()
    stats = import_text(text, replace=args.replace)
    for warning in stats["warnings"]:
        print("[경고]", warning)
    print(f"완료: 총 {stats['total']}곡 (추가 {stats['inserted']}, 갱신 {stats['updated']})")


if __name__ == "__main__":
    main()
