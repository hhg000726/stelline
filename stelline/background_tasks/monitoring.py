"""YouTube 조회수 감시와 만료 데이터 정리를 담당하는 백그라운드 작업."""

from datetime import datetime
import logging
import threading
import time

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from stelline.config import API_CHECK_INTERVAL, API_KEY, MAX_RESULTS, PLAYLIST_ID, PROJECT_ID, SERVICE_ACCOUNT_FILE
from stelline.database.connection import database_cursor

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
        response = requests.get("https://www.googleapis.com/youtube/v3/playlistItems", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        for item in data.get("items", []):
            video_ids.append(item["snippet"]["resourceId"]["videoId"])
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    for start in range(0, len(video_ids), MAX_RESULTS):
        response = requests.get(
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
    cursor.execute("SELECT token FROM fcm_tokens")
    for row in cursor.fetchall():
        payload = {"message": {"token": row["token"], "data": {
            "title": song["title"],
            "body": f"{song['count'] // 100000}0만회 달성!",
            "image": f"https://img.youtube.com/vi/{song['video_id']}/maxresdefault.jpg",
            "video_url": f"https://www.youtube.com/watch?v={song['video_id']}",
        }}}
        response = requests.post(
            f"https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        if response.status_code == 404 and "UNREGISTERED" in response.text:
            cursor.execute("DELETE FROM fcm_tokens WHERE token = %s", (row["token"],))
        elif not response.ok:
            logging.error("FCM 알림 실패 (%s): %s", response.status_code, response.text)


def update_song_counts(cursor, songs, access_token):
    for song in songs:
        cursor.execute("SELECT count FROM song_counts WHERE video_id = %s", (song["video_id"],))
        existing = cursor.fetchone()
        if existing is None:
            cursor.execute(
                "INSERT INTO song_counts (title, video_id, count, counted_time) VALUES (%s, %s, %s, %s)",
                (song["title"], song["video_id"], song["count"], datetime(2000, 1, 1)),
            )
        elif existing["count"] // 100000 < song["count"] // 100000:
            send_milestone_notifications(cursor, access_token, song)
            cursor.execute(
                "UPDATE song_counts SET count = %s, counted_time = %s WHERE video_id = %s",
                (song["count"], datetime.now(), song["video_id"]),
            )


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
