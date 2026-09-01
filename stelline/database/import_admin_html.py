"""관리자 HTML 스냅샷을 개발 DB의 시드 데이터로 가져온다.

운영 DB에는 절대 실행하지 않는다. FCM 토큰과 제거된 게임 데이터는 의도적으로
가져오지 않는다.
"""

import argparse
from pathlib import Path

from bs4 import BeautifulSoup

from stelline.config import APP_ENV
from stelline.database.connection import get_connection
from stelline.database.migrate import apply_migrations

IMPORT_COLUMNS = {
    "song_infos": ("video_id", "query", "risk"),
    "songs_data": ("video_id", "query", "searched_time"),
    "recent_data": ("video_id", "query", "searched_time"),
    "record_main": ("copy_count",),
    "record_search": ("total_plays", "total_play_time", "copy_count"),
    "targets": ("name", "title", "url_number", "expires_at"),
    "events": ("title", "link", "expires_at"),
    "twits": ("title", "time", "tags", "keywords", "expires_at"),
    "song_counts": ("title", "video_id", "count", "counted_time"),
    "offline": ("name", "location_name", "description", "latitude", "longitude", "start_date", "end_date", "address", "always"),
}

INTEGER_COLUMNS = {"risk", "url_number", "copy_count", "total_plays", "count", "always"}
FLOAT_COLUMNS = {"searched_time", "total_play_time", "latitude", "longitude"}


def read_html(path):
    raw = Path(path).read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("지원하지 않는 HTML 문자 인코딩입니다.")


def normalize_value(column, value):
    value = value.strip()
    if not value or value.lower() == "none":
        return None
    if column == "always":
        return int(value.lower() in {"1", "true", "yes", "on"})
    if column in INTEGER_COLUMNS:
        return int(value)
    if column in FLOAT_COLUMNS:
        return float(value)
    return value


def parse_snapshot(path):
    soup = BeautifulSoup(read_html(path), "html.parser")
    snapshot = {}
    for section in soup.select("details"):
        summary = section.find("summary")
        if summary is None:
            continue
        table_name = summary.get_text(strip=True)
        expected_columns = IMPORT_COLUMNS.get(table_name)
        if expected_columns is None:
            continue
        headers = [header.get_text(strip=True) for header in section.select("thead th")]
        if not headers:
            snapshot[table_name] = []
            continue
        if any(column not in expected_columns for column in headers):
            raise ValueError(f"{table_name}: 지원하지 않는 컬럼이 포함되어 있습니다: {headers}")
        rows = []
        for html_row in section.select("tbody tr"):
            cells = html_row.find_all("td", recursive=False)
            values = [cell.get_text(strip=True) for cell in cells[:len(headers)]]
            if len(values) != len(headers):
                continue
            rows.append({column: normalize_value(column, value) for column, value in zip(headers, values)})
        snapshot[table_name] = rows
    return snapshot


def import_snapshot(snapshot, replace):
    """스냅샷을 DB에 적재한다.

    한 표의 행들은 같은 머리글에서 나오므로 열 구성이 같다. 그래서 행마다 왕복하지 않고
    열 구성이 같은 묶음끼리 executemany 로 한 번에 넣는다.
    """
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for table_name, rows in snapshot.items():
                if replace:
                    cursor.execute(f"DELETE FROM `{table_name}`")
                batches = {}
                for row in rows:
                    batches.setdefault(tuple(row), []).append([row[column] for column in row])
                for columns, values in batches.items():
                    placeholders = ", ".join(["%s"] * len(columns))
                    names = ", ".join(f"`{column}`" for column in columns)
                    cursor.executemany(
                        f"INSERT INTO `{table_name}` ({names}) VALUES ({placeholders})",
                        values,
                    )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description="관리자 HTML을 개발 DB에 적재합니다.")
    parser.add_argument("html_file", help="관리자 화면에서 저장한 HTML 파일 경로")
    parser.add_argument("--replace", action="store_true", help="HTML에 포함된 개발 테이블을 비우고 스냅샷으로 교체")
    parser.add_argument("--dry-run", action="store_true", help="DB를 변경하지 않고 읽을 테이블과 행 수만 출력")
    args = parser.parse_args()

    if APP_ENV != "development":
        raise RuntimeError("이 도구는 APP_ENV=development에서만 실행할 수 있습니다.")
    snapshot = parse_snapshot(args.html_file)
    print("Import candidates:")
    for table_name, rows in snapshot.items():
        print(f"- {table_name}: {len(rows)} rows")
    if args.dry_run:
        return
    if not args.replace:
        raise RuntimeError("개발 DB 교체는 --replace 옵션을 명시해야 합니다.")

    apply_migrations()
    import_snapshot(snapshot, replace=True)
    print("Development database import completed. fcm_tokens and leaderboard were not imported.")


if __name__ == "__main__":
    main()
