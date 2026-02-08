from stelline.config import *
from stelline.database.db_connection import get_rds_connection
import logging, requests, time
from datetime import datetime
from google.oauth2 import service_account
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/firebase.messaging']

def get_access_token():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    credentials.refresh(Request())
    return credentials.token

def get_songs():
    URL = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={PLAYLIST_ID}&maxResults={MAX_RESULTS}&key={API_KEY}"
    songs = []
    video_ids = []
    next_page_token = None
    songs_for_counts = []

    try:
        while True:
            try:
                response = requests.get(URL + (f"&pageToken={next_page_token}" if next_page_token else ""), timeout=10)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logging.error(f"YouTube API 요청 실패: {e}")
                return []
            
            data = response.json()
            for item in data.get("items", []):
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_ids.append(video_id)
                songs.append({
                    "title": item["snippet"]["title"],
                    "video_id": video_id
                })            

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

        for i in range(0, len(video_ids), MAX_RESULTS):
            video_id_str = ",".join(video_ids[i:i + MAX_RESULTS])
            video_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={video_id_str}&key={API_KEY}"
            video_response = requests.get(video_url).json()

            for item in video_response.get("items", []):
                video_id = item["id"]
                published_at = item["snippet"]["publishedAt"]
                title = item["snippet"]["title"]
                view_count = int(item.get("statistics", {}).get("viewCount", 0))

                for song in songs:
                    if song["video_id"] == video_id:
                        song["date"] = published_at

                songs_for_counts.append({
                    "title": title,
                    "video_id": video_id,
                    "count": view_count
                })

        return {"all_songs": songs, "songs_for_counts": songs_for_counts}
    except Exception as e:
        logging.error(f"YouTube API에서 곡을 가져오는 중 오류 발생: {e}")
        return []
    
# 주기적으로 유튜브 데이터 가져오기
def youtube_api_process(all_songs):
    while True:
        try:
            new_songs = get_songs()
            if new_songs.get("all_songs") and new_songs.get("all_songs") != all_songs:
                all_songs.clear()
                all_songs["all_songs"] = new_songs.get("all_songs")
            else:
                logging.warning("YouTube Playlist API에서 새로운 곡 데이터를 가져오지 못함.")
                
            access_token = get_access_token()
            conn = get_rds_connection()
            
            with conn.cursor() as cursor:
                sql = "SELECT * FROM twits WHERE expires_at < %s"
                cursor.execute(sql, (datetime.now(),))
                targets = cursor.fetchall()
                if targets:
                    sql = """
                            DELETE FROM twits
                            WHERE expires_at < %s
                        """
                    cursor.execute(sql, (datetime.now(),))
                    conn.commit()
                    for target in targets:
                        logging.info(f"만료된 트윗 데이터 삭제: {target['title']}")
                        
            with conn.cursor() as cursor:
                sql = "SELECT * FROM events WHERE expires_at < %s"
                cursor.execute(sql, (datetime.now(),))
                events = cursor.fetchall()
                if events:
                    sql = """
                            DELETE FROM events
                            WHERE expires_at < %s
                        """
                    cursor.execute(sql, (datetime.now(),))
                    conn.commit()
                    for event in events:
                        logging.info(f"만료된 펀딩 데이터 삭제: {event['title']}")
                        
            with conn.cursor() as cursor:
                sql = "SELECT * FROM targets WHERE expires_at < %s"
                cursor.execute(sql, (datetime.now(),))
                targets = cursor.fetchall()
                if targets:
                    sql = """
                            DELETE FROM targets
                            WHERE expires_at < %s
                        """
                    cursor.execute(sql, (datetime.now(),))
                    conn.commit()
                    for target in targets:
                        logging.info(f"만료된 벅스 데이터 삭제: {target['title']}")
                        
            with conn.cursor() as cursor:
                sql = "SELECT * FROM offline WHERE end_date < %s"
                cursor.execute(sql, (datetime.now(),))
                offlines = cursor.fetchall()
                if offlines:
                    sql = """
                            DELETE FROM offline
                            WHERE end_date < %s
                        """
                    cursor.execute(sql, (datetime.now(),))
                    conn.commit()
                    for offline in offlines:
                        logging.info(f"만료된 오프라인 데이터 삭제: {offline['title']}")
                        
            with conn.cursor() as cursor:
                sql = "SELECT * FROM recent_data WHERE searched_time < %s"
                cursor.execute(sql, (time.time() - 7 * 24 * 3600,))
                old_recents = cursor.fetchall()
                if old_recents:
                    sql = """
                            DELETE FROM recent_data
                            WHERE searched_time < %s
                        """
                    cursor.execute(sql, (time.time() - 7 * 24 * 3600,))
                    conn.commit()
                    for old_recent in old_recents:
                        logging.info(f"오래된 검색 안됨 데이터 삭제: {old_recent['video_id']}")
                    
            try:
                for song in new_songs.get("songs_for_counts", []):
                    with conn.cursor() as cursor:
                        sql = "SELECT * FROM song_counts WHERE video_id = %s"
                        cursor.execute(sql, (song["video_id"],))
                        existing_song = cursor.fetchone()
                    if existing_song and existing_song["count"] // 100000 < song["count"] // 100000:
                        with conn.cursor() as cursor:
                            sql = "SELECT token FROM fcm_tokens"
                            cursor.execute(sql, )
                            rows = cursor.fetchall()
                            tokens = [row['token'] for row in rows]
                            for token in tokens:
                                url = f"https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send"
                                headers = {
                                    "Authorization": f"Bearer {access_token}",
                                    "Content-Type": "application/json"
                                }
                                payload = {
                                    "message":{
                                        "token": token,
                                        "data": {
                                            "title": song['title'],
                                            "body": f"{song['count'] // 100000}0만회 달성!",
                                            "image": f"https://img.youtube.com/vi/{song['video_id']}/maxresdefault.jpg",
                                            "video_url": f"https://www.youtube.com/watch?v={song['video_id']}"
                                        },
                                        "webpush": {
                                            "headers": {
                                                "TTL": "86400"  # 24시간 동안 재전송 시도
                                            }
                                        },
                                        "android": {
                                            "ttl": "86400s",
                                            "priority": "HIGH",
                                            "notification": {
                                                "channel_id": "high_importance_channel",
                                                "default_vibrate_timings": True,
                                                "default_sound": True,
                                                "visibility": "PUBLIC",
                                                "click_action": "OPEN_YOUTUBE"
                                            }
                                        }
                                    }
                                }
                                response = requests.post(url, headers=headers, json=payload)
                                if response.status_code != 200:
                                    logging.info(f"FCM 알림 실패 ({response.status_code}): {response.text}")
                                    if response.status_code == 404 and "UNREGISTERED" in response.text:
                                        sql = """
                                            DELETE FROM fcm_tokens
                                            WHERE token = %s
                                        """
                                        cursor.execute(sql, (token,))
                                        logging.info(f"토큰 만료 혹은 등록 해제됨, 삭제 처리: {token}")
                                    else:
                                        logging.error(f"FCM 알림 발송 중 오류 발생: {response.text}")
                        with conn.cursor() as cursor:
                            sql = """
                                UPDATE song_counts
                                SET count = %s, counted_time = %s
                                WHERE video_id = %s
                            """
                            cursor.execute(sql, (song["count"], datetime.now(), song["video_id"]))
                            conn.commit()
                    if not existing_song:
                        with conn.cursor() as cursor:
                            sql = """
                                INSERT INTO song_counts (title, video_id, count, counted_time)
                                VALUES (%s, %s, %s, %s)
                            """
                            cursor.execute(sql, (song["title"], song["video_id"], song["count"], datetime(2000, 1, 1)))
                            conn.commit()
            except Exception as e:
                logging.error(f"노래 카운트 업데이트 오류: {e}")
                continue
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"데이터 업데이트 오류: {e}")
        
        time.sleep(API_CHECK_INTERVAL)