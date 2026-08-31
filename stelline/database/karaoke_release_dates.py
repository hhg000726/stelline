"""커버 곡의 발매일을 연결된 유튜브 영상의 업로드 날짜로 채운다.

관리자 화면이나 붙여넣기 등록으로 곡에 유튜브 영상을 적어 두면,
`python -m stelline.database.karaoke_release_dates` 로 비어 있는 발매일을 한 번에 채운다.

YouTube Data API의 `videos.list`는 호출 1회당 쿼터 1을 쓰고 영상 50개까지 한 번에 받는다.
그래서 곡마다 부르지 않고 50개씩 묶어 부른다(커버 300곡이면 6회, 쿼터 6).
이미 발매일이 있는 곡은 건드리지 않으며, 삭제·비공개로 응답에 없는 영상은 기록만 남기고 넘어간다.
"""

import argparse
import logging
import re
from datetime import datetime, timedelta, timezone

import requests

from stelline.config import API_KEY
from stelline.database.connection import get_connection

YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

# videos.list가 한 번에 받아 주는 최대 개수. 쿼터는 호출 수로 매겨지니 꽉 채워 보낸다.
BATCH_SIZE = 50

# 업로드 시각은 UTC로 오지만, 발매일은 한국 기준 날짜로 적어야 목록의 다른 날짜와 맞는다.
KST = timezone(timedelta(hours=9))

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
URL_PATTERNS = (
    re.compile(r"[?&]v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/(?:embed|shorts|live|v)/([A-Za-z0-9_-]{11})"),
)


def extract_video_id(value):
    """영상 ID나 유튜브 주소에서 11자 영상 ID를 뽑는다. 알아볼 수 없으면 None."""
    text = (value or "").strip()
    if not text:
        return None
    if VIDEO_ID_PATTERN.match(text):
        return text
    for pattern in URL_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def _batches(items, size=BATCH_SIZE):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _upload_date(published_at):
    """`2024-08-01T15:00:00Z` 같은 값을 한국 날짜 문자열로 바꾼다."""
    if not published_at:
        return None
    try:
        moment = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        logging.warning("업로드 시각을 해석하지 못했습니다: %s", published_at)
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(KST).date().isoformat()


def fetch_upload_dates(video_ids, api_key=None):
    """영상 ID 목록을 50개씩 묶어 업로드 날짜를 가져온다.

    반환값은 {영상 ID: 'YYYY-MM-DD'}이다. 삭제·비공개 영상은 응답에 없으므로 빠진다.
    한 묶음이 실패해도 나머지는 계속 처리한다.
    """
    key = api_key or API_KEY
    if not key:
        raise RuntimeError("YouTube API 키가 없습니다. API_KEY 환경 변수를 설정하세요.")

    dates = {}
    for batch in _batches(list(video_ids)):
        try:
            response = requests.get(
                YOUTUBE_VIDEOS_URL,
                params={"part": "snippet", "id": ",".join(batch), "key": key},
                timeout=10,
            )
            response.raise_for_status()
            items = response.json().get("items", [])
        except Exception:
            logging.exception("유튜브 업로드 날짜 조회 실패: %s건 건너뜁니다.", len(batch))
            continue
        for item in items:
            date_value = _upload_date(item.get("snippet", {}).get("publishedAt"))
            if date_value:
                dates[item["id"]] = date_value
    return dates


def _songs_to_fill(cursor, category, overwrite):
    conditions = ["youtube_video_id IS NOT NULL", "youtube_video_id <> ''"]
    params = []
    if category:
        conditions.append("category = %s")
        params.append(category)
    if not overwrite:
        conditions.append("release_date IS NULL")
    cursor.execute(
        "SELECT id, title, artist, youtube_video_id, release_date FROM karaoke_songs"
        f" WHERE {' AND '.join(conditions)} ORDER BY id",
        params,
    )
    return cursor.fetchall()


def backfill_release_dates(category="cover", overwrite=False, dry_run=False, api_key=None):
    """발매일이 비어 있는 곡을 유튜브 업로드 날짜로 채우고 결과를 요약해 돌려준다."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            songs = _songs_to_fill(cursor, category, overwrite)
    finally:
        connection.close()

    unresolved = [song for song in songs if not extract_video_id(song["youtube_video_id"])]
    for song in unresolved:
        logging.warning(
            "유튜브 영상 주소를 알아볼 수 없습니다: %s - %s (%s)",
            song["title"], song["artist"], song["youtube_video_id"],
        )

    targets = [(song, extract_video_id(song["youtube_video_id"])) for song in songs]
    targets = [(song, video_id) for song, video_id in targets if video_id]
    if not targets:
        logging.info("발매일을 채울 커버 곡이 없습니다.")
        return {"candidates": len(songs), "updated": 0, "unchanged": 0, "missing": [], "invalid": len(unresolved)}

    dates = fetch_upload_dates(sorted({video_id for _, video_id in targets}), api_key=api_key)

    updates, missing, unchanged = [], [], 0
    for song, video_id in targets:
        upload_date = dates.get(video_id)
        if not upload_date:
            # 영상이 지워졌거나 비공개면 응답에 없다. 기록만 남기고 다음 곡으로 넘어간다.
            missing.append(f"{song['title']} - {song['artist']} ({video_id})")
            logging.warning("업로드 날짜를 가져오지 못했습니다: %s - %s (%s)", song["title"], song["artist"], video_id)
            continue
        if song["release_date"] and song["release_date"].isoformat() == upload_date:
            unchanged += 1
            continue
        updates.append((upload_date, song["id"]))

    if updates and not dry_run:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.executemany("UPDATE karaoke_songs SET release_date = %s WHERE id = %s", updates)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    stats = {
        "candidates": len(songs),
        "updated": len(updates),
        "unchanged": unchanged,
        "missing": missing,
        "invalid": len(unresolved),
        "dry_run": dry_run,
    }
    logging.info(
        "커버 곡 발매일 채우기 완료: 대상=%s, 갱신=%s, 그대로=%s, 실패=%s, 주소오류=%s, 미리보기=%s",
        stats["candidates"], stats["updated"], stats["unchanged"], len(missing), stats["invalid"], dry_run,
    )
    return stats


def main():
    parser = argparse.ArgumentParser(description="커버 곡의 발매일을 유튜브 업로드 날짜로 채웁니다.")
    parser.add_argument("--all-categories", action="store_true", help="커버뿐 아니라 모든 곡을 대상으로 합니다.")
    parser.add_argument("--overwrite", action="store_true", help="이미 발매일이 있는 곡도 업로드 날짜로 덮어씁니다.")
    parser.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 결과만 확인합니다.")
    args = parser.parse_args()

    stats = backfill_release_dates(
        category=None if args.all_categories else "cover",
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    for line in stats["missing"]:
        print("[실패]", line)
    print(
        f"완료: 대상 {stats['candidates']}곡 중 {stats['updated']}곡 갱신"
        f" (그대로 {stats['unchanged']}, 실패 {len(stats['missing'])}, 주소 오류 {stats['invalid']})"
        + (" · 미리보기라 저장하지 않았습니다." if stats["dry_run"] else "")
    )


if __name__ == "__main__":
    main()
