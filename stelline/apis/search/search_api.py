import logging, time, requests, random

from stelline.config import *
from stelline.database.db_connection import get_rds_connection

def load_song_infos():
    logging.info("곡 정보 불러오는 중..")
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM song_infos"
            cursor.execute(sql)
            result = cursor.fetchall()
        logging.info("RDS에서 곡 정보 불러오기 성공")
    except Exception as e:
        logging.error(f"RDS 곡 정보 불러오기 실패: {e}")
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


def search_api():
    song_infos = load_song_infos()
    recent = load_recent_data()
    logging.info(f"검색 시작")
    url = "https://www.googleapis.com/youtube/v3/search"
    not_searched = []
    search_targets = [
        {"query": row["query"], "video_id": row["video_id"]}
        for row in recent
    ]
    # 25개로 맞추기 위해 필요한 개수 계산
    needed = 25 - len(search_targets)

    # 중복 방지: converted에 이미 있는 video_id는 제외
    existing_ids = {item["video_id"] for item in search_targets}
    available = [info for info in song_infos if info["video_id"] not in existing_ids]

    # 부족한 만큼 랜덤 추출
    additional = random.sample(available, min(needed, len(available)))

    # 추가
    search_targets.extend(additional)

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
            logging.info(all_songs)
            searched_time = new_songs["searched_time"]
            logging.info(searched_time)
            conn = get_rds_connection()
            try:
                with conn.cursor() as cursor:
                    sql = """
                        SELECT * FROM songs_data;
                        """
                    cursor.execute(sql)
                    result = cursor.fetchall()
                    logging.info(result)
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
                        logging.info(video_id, query, searched_time)
                    sql = """
                        SELECT * FROM songs_data;
                        """
                    cursor.execute(sql)
                    result = cursor.fetchall()
                    logging.info(result)
                    sql = """
                        INSERT INTO recent_data (video_id, query, searched_time)
                        SELECT video_id, query, searched_time
                        FROM songs_data
                        ON DUPLICATE KEY UPDATE
                            searched_time = VALUES(searched_time)
                    """
                    cursor.execute(sql)

                    logging.info("검색 데이터 업데이트 완료!")
            except Exception as e:
                logging.error(f"RDS search 업데이트 실패: {e}")
            finally:
                conn.close()

        except Exception as e:
            logging.error(f"검색 업데이트 오류: {e}")
        
        time.sleep(SEARCH_API_INTERVAL)