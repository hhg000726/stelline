"""YouTube 조회수 감시와 만료 데이터 정리를 담당하는 백그라운드 작업."""

from datetime import datetime
import logging
import threading
import time

from google.auth.transport.requests import Request
from google.oauth2 import service_account

from stelline.config import API_CHECK_INTERVAL, API_KEY, MAX_RESULTS, PLAYLIST_ID, PROJECT_ID, SERVICE_ACCOUNT_FILE
from stelline.database.connection import database_cursor
from stelline.http_client import SESSION

SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]


def get_access_token():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    credentials.refresh(Request())
    return credentials.token


def get_playlist_videos():
    """플레이리스트의 영상 제목·조회수를 가져온다."""
    songs = []
    video_ids = []
    page_token = None

    while True:
        params = {
            "part": "snippet",
            "playlistId": PLAYLIST_ID,
            "maxResults": MAX_RESULTS,
            "key": API_KEY,
        }
        if page_token:
            params["pageToken"] = page_token
        response = SESSION.get("https://www.googleapis.com/youtube/v3/playlistItems", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        for item in data.get("items", []):
            video_ids.append(item["snippet"]["resourceId"]["videoId"])
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    for start in range(0, len(video_ids), MAX_RESULTS):
        response = SESSION.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "snippet,statistics", "id": ",".join(video_ids[start:start + MAX_RESULTS]), "key": API_KEY},
            timeout=10,
        )
        response.raise_for_status()
        for item in response.json().get("items", []):
            songs.append({
                "title": item["snippet"]["title"],
                "video_id": item["id"],
                "count": int(item.get("statistics", {}).get("viewCount", 0)),
            })
    return songs


def remove_expired_data(cursor):
    now = datetime.now()
    expiry_tables = (("twits", "expires_at"), ("events", "expires_at"), ("targets", "expires_at"), ("offline", "end_date"))
    for table, column in expiry_tables:
        cursor.execute(f"DELETE FROM {table} WHERE {column} < %s", (now,))
    cursor.execute("DELETE FROM recent_data WHERE searched_time < %s", (time.time() - 7 * 24 * 3600,))


def send_milestone_notifications(cursor, access_token, song):
    """등록된 모든 토큰에 달성 알림을 보낸다.

    같은 호스트로 토큰 수만큼 연달아 POST 하므로 공용 세션으로 연결을 재사용한다.
    사라진 토큰은 모아 두었다가 마지막에 한 번에 지운다(왕복 횟수를 줄인다).
    """
    cursor.execute("SELECT token FROM fcm_tokens")
    url = f"https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = {
        "title": song["title"],
        "body": f"{song['count'] // 100000}0만회 달성!",
        "image": f"https://img.youtube.com/vi/{song['video_id']}/maxresdefault.jpg",
        "video_url": f"https://www.youtube.com/watch?v={song['video_id']}",
    }

    unregistered = []
    for row in cursor.fetchall():
        response = SESSION.post(
            url,
            headers=headers,
            json={"message": {"token": row["token"], "data": data}},
            timeout=10,
        )
        if response.status_code == 404 and "UNREGISTERED" in response.text:
            unregistered.append((row["token"],))
        elif not response.ok:
            logging.error("FCM 알림 실패 (%s): %s", response.status_code, response.text)

    if unregistered:
        cursor.executemany("DELETE FROM fcm_tokens WHERE token = %s", unregistered)


def update_song_counts(cursor, songs, access_token):
    """조회수를 갱신하고, 10만 단위를 새로 넘긴 곡만 알린다.

    예전에는 곡마다 SELECT 를 한 번씩 던져 플레이리스트 크기만큼 왕복이 생겼다.
    지금은 저장된 조회수를 한 번에 읽어 두고 메모리에서 비교한다.
    """
    cursor.execute("SELECT video_id, count FROM song_counts")
    stored_counts = {row["video_id"]: row["count"] for row in cursor.fetchall()}

    for song in songs:
        existing = stored_counts.get(song["video_id"])
        if existing is None:
            cursor.execute(
                "INSERT INTO song_counts (title, video_id, count, counted_time) VALUES (%s, %s, %s, %s)",
                (song["title"], song["video_id"], song["count"], datetime(2000, 1, 1)),
            )
            # 같은 영상이 목록에 두 번 들어와도 예전처럼 한 번만 저장되도록 방금 쓴 값을 반영한다.
            stored_counts[song["video_id"]] = song["count"]
        elif existing // 100000 < song["count"] // 100000:
            send_milestone_notifications(cursor, access_token, song)
            cursor.execute(
                "UPDATE song_counts SET count = %s, counted_time = %s WHERE video_id = %s",
                (song["count"], datetime.now(), song["video_id"]),
            )
            stored_counts[song["video_id"]] = song["count"]


def monitoring_process():
    while True:
        try:
            songs = get_playlist_videos()
            access_token = get_access_token()
            with database_cursor() as cursor:
                remove_expired_data(cursor)
                update_song_counts(cursor, songs, access_token)
            logging.info("YouTube 조회수 및 만료 데이터 동기화 완료")
        except Exception:
            logging.exception("조회수 감시 작업 실패")
        time.sleep(API_CHECK_INTERVAL)


def start_monitoring():
    threading.Thread(target=monitoring_process, daemon=True, name="monitoring").start()
