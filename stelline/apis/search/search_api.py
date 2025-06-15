import logging, time, requests, random

from stelline.config import *
from stelline.database.db_connection import get_rds_connection

def load_song_infos():
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM song_infos"
            cursor.execute(sql)
            result = cursor.fetchall()
    except Exception as e:
        logging.error(f"RDS 곡 정보 불러오기 실패: {e}")
        result = []
    finally:
        conn.close()
    return result

def load_songs_data():
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM songs_data"
            cursor.execute(sql)
            rows = cursor.fetchall()
            all_songs = []
            for row in rows:
                all_songs.append({
                    "query": row.get("query"),
                    "video_id": row.get("video_id")
                })
            searched_time = rows[0]["searched_time"] if rows else 0
    except Exception as e:
        all_songs = []
        searched_time = 0
        logging.error(f"RDS songs 정보 불러오기 실패: {e}")
    finally:
        conn.close()
        
    return all_songs, searched_time

def load_recent_data():
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM recent_data"
            cursor.execute(sql)
            recent = cursor.fetchall()
    except Exception as e:
        recent = []
        logging.error(f"RDS recent 정보 불러오기 실패: {e}")
    finally:
        conn.close()
    return recent

def update_risk(video_id, risk):
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE song_infos
                SET risk = %s
                WHERE video_id = %s
            """
            cursor.execute(sql, (risk, video_id))
            conn.commit()
    except Exception as e:
        logging.error(f"RDS risk 업데이트 실패: {e}")
    finally:
        conn.close()

def search_api():
    song_infos = load_song_infos()
    logging.info(f"검색 시작")
    not_searched = []
    url = "https://www.googleapis.com/youtube/v3/search"
    search_targets = []

    for risk_level in reversed(range(29)):
        candidates = [info for info in song_infos if info.get("risk") == risk_level]
        
        # 아직 25개 미만이면 후보 추가
        remaining = 25 - len(search_targets)
        if remaining <= 0:
            break
        
        if len(candidates) > remaining:
            search_targets.extend(random.sample(candidates, remaining))
            break
        else:
            search_targets.extend(candidates)

    for song_info in search_targets:
        query = song_info["query"]
        video_id = song_info["video_id"]
        
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 3,
            "key": SEARCH_API_KEY
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # HTTP 에러 체크 (4xx, 5xx)
            data = response.json()
            video_ids = [item["id"]["videoId"] for item in data["items"]]
            if video_id not in video_ids:
                not_searched.append({"query": query, "video_id": video_id})
                update_risk(video_id, 28)
            else:
                update_risk(video_id, max(song_info["risk"] - 1, 0))
        except requests.RequestException as e:
            logging.error(f"API 요청 실패: {e}")
            continue
    
    return {"all_songs": not_searched, "searched_time": time.time()}

# 주기적으로 검색 데이터 가져오기
def search_api_process():
    logging.info("주기적 검색 시작됨")
    while True:
        try:
            new_songs = search_api()
            all_songs = new_songs["all_songs"]
            searched_time = new_songs["searched_time"]
            conn = get_rds_connection()
            try:
                with conn.cursor() as cursor:
                    sql = """
                        TRUNCATE TABLE songs_data;
                        """
                    cursor.execute(sql)
                    
                    for item in all_songs:
                        video_id = item.get("video_id", "")
                        query = item.get("query", "")
                        sql = """
                        INSERT INTO songs_data (video_id, query, searched_time)
                        VALUES (%s, %s, %s)
                        """
                        cursor.execute(sql, (video_id, query, searched_time))
                    conn.commit()

                    logging.info("검색 데이터 업데이트 완료!")
            except Exception as e:
                logging.error(f"RDS search 업데이트 실패: {e}")
            finally:
                conn.close()

        except Exception as e:
            logging.error(f"검색 업데이트 오류: {e}")
        
        time.sleep(SEARCH_API_INTERVAL - time.time() % (SEARCH_API_INTERVAL))