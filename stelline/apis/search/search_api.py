import json, logging, random, re, requests, time

from stelline.config import *
from stelline.database.db_connection import get_rds_connection

LAST_SEARCH_FILE = "last_search_time.txt"

def load_last_search_time():
    try:
        if not os.path.exists(LAST_SEARCH_FILE):
            with open(LAST_SEARCH_FILE, "w") as f:
                f.write("0")
            return 0

        with open(LAST_SEARCH_FILE, "r") as f:
            return float(f.read().strip())
    except:
        logging.error("마지막 검색 시간 불러오기 실패")
        return 0

def save_last_search_time(t):
    with open(LAST_SEARCH_FILE, "w") as f:
        f.write(str(t))
        
lastSearchTime = load_last_search_time()

def load_song_infos():
    conn = None
    try:
        conn = get_rds_connection()
        with conn.cursor() as cursor:
            sql = "SELECT * FROM song_infos"
            cursor.execute(sql)
            result = cursor.fetchall()
    except Exception as e:
        logging.error(f"RDS 곡 정보 불러오기 실패: {e}")
        result = []
    finally:
        if conn:
            conn.close()
    return result

def load_songs_data():
    global lastSearchTime
    conn = None
    try:
        conn = get_rds_connection()
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
            searched_time = lastSearchTime
    except Exception as e:
        all_songs = []
        searched_time = 0
        logging.error(f"RDS songs 정보 불러오기 실패: {e}")
    finally:
        if conn:
            conn.close()
        
    return all_songs, searched_time

def load_recent_data():
    conn = None
    try:
        conn = get_rds_connection()
        with conn.cursor() as cursor:
            sql = "SELECT * FROM recent_data"
            cursor.execute(sql)
            recent = cursor.fetchall()
    except Exception as e:
        recent = []
        logging.error(f"RDS recent 정보 불러오기 실패: {e}")
    finally:
        if conn:
            conn.close()
    return recent

def update_risk(video_id, risk):
    conn = None
    try:
        conn = get_rds_connection()
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
        if conn:
            conn.close()

def crawl_search_api(songs):
    not_searched = []
    baseUrl = "https://www.youtube.com/results"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    for case in songs:
        time.sleep(random.uniform(3, 8))
        query = case["query"]
        params = {"search_query": query}
        video_id = case["video_id"]
        try:
            r = requests.get(baseUrl, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            html = r.text
            match = re.search(r"ytInitialData\s*=\s*({.*?});", html, re.DOTALL)
            if not match:
                logging.error(f"크롤링 데이터 파싱 실패: {query}")
                continue
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                logging.error(f"JSON 파싱 실패: {query}")
                continue
            video_ids = []
            contents = data.get("contents", {}) \
                .get("twoColumnSearchResultsRenderer", {}) \
                .get("primaryContents", {}) \
                .get("sectionListRenderer", {}) \
                .get("contents", [])
            for section in contents:
                if len(video_ids) >= 3:
                    break
                items = section.get("itemSectionRenderer", {}).get("contents", [])
                for item in items:
                    if len(video_ids) >= 3:
                        break
                    video = item.get("videoRenderer")
                    if video:
                        video_ids.append(video["videoId"])
            if video_id not in video_ids:
                not_searched.append({"query": query, "video_id": video_id})
                update_risk(video_id, 28)
            else:
                update_risk(video_id, max(case["risk"] - 1, 0))
            
        except requests.RequestException as e:
            logging.error(f"크롤링 실패: {e}")
            return {"all_songs": songs, "searched_time": time.time()}
        
    return {"all_songs": not_searched, "searched_time": time.time()}

def search_api():
    isQuotaExceeded = False
    
    song_infos = load_song_infos()
    logging.info(f"검색 시작")
    not_searched = []
    url = "https://www.googleapis.com/youtube/v3/search"
    search_targets = []
    risk_zero_songs = [info for info in song_infos if info.get("risk") == 0]
    
    for risk_level in reversed(range(1, 29)):
        search_targets.extend([info for info in song_infos if info.get("risk") == risk_level])
        if len(search_targets) >= 12:
            search_targets = search_targets[:12]
            break
    
    logging.info(f"[1차 검사 시작] risk_zero_songs={len(risk_zero_songs)}, search_targets={len(search_targets)}")

    remainingQuotes = 25
    
    while remainingQuotes > len(not_searched) + 1:
        
        song = None
        
        if search_targets:
            song = search_targets.pop(0)
        else:
            if not risk_zero_songs:
                break
            song = risk_zero_songs.pop(random.randrange(len(risk_zero_songs)))
        
        if not song:
            break
        
        if song:
            song_info = song
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
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()  # HTTP 에러 체크 (4xx, 5xx)
                data = response.json()
                items = data.get("items", [])
                video_ids = [item["id"]["videoId"] for item in items if "id" in item]
                if video_id not in video_ids:
                    not_searched.append({"query": query, "video_id": video_id, "risk": song_info["risk"]})
            except requests.RequestException as e:
                isQuotaExceeded = True
                logging.error(f"API 요청 실패: {e}")
            
            remainingQuotes -= 1
    
    logging.info(f"[1차 검사 종료] remainingQuotes={remainingQuotes}, not_searched={len(not_searched)}")

    i = 0

    while i < len(not_searched) and remainingQuotes > 0:
        song = not_searched[i]
        query = song["query"]
        video_id = song["video_id"]

        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 3,
            "key": SEARCH_API_KEY
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()  # HTTP 에러 체크 (4xx, 5xx)
            data = response.json()
            items = data.get("items", [])
            video_ids = [item["id"]["videoId"] for item in items if "id" in item]
            if video_id not in video_ids:
                i += 1
                update_risk(video_id, 28)
            else:
                not_searched.pop(i)
                update_risk(video_id, max(song["risk"] - 1, 0))
        except requests.RequestException as e:
            i += 1
            isQuotaExceeded = True
            logging.error(f"API 요청 실패: {e}")
            
        remainingQuotes -= 1
    
    logging.info(f"[2차 검사 종료] remainingQuotes={remainingQuotes}, not_searched={len(not_searched)}")
    
    not_searched = crawl_search_api(not_searched)["all_songs"]
    
    logging.info(f"[최종 결과] 총 실패곡={len(not_searched)}")

    return {"all_songs": not_searched, "searched_time": time.time(), "isQuotaExceeded": isQuotaExceeded}

# 주기적으로 검색 데이터 가져오기
def search_api_process(by_admin=False):
    logging.info("주기적 검색 시작됨")
    global lastSearchTime

    while True:
        try:
            new_songs = search_api()

            if new_songs.get("isQuotaExceeded"):
                logging.info("쿼터 초과")
            else:
                lastSearchTime = new_songs["searched_time"]
                save_last_search_time(lastSearchTime)
                all_songs = new_songs["all_songs"]
                save_to_db(all_songs, new_songs["searched_time"])
                logging.info("검색 데이터 업데이트 완료!")

        except Exception as e:
            logging.error(f"검색 업데이트 오류: {e}")

        if by_admin:
            break

        sleep_until_next_interval()
        
def save_to_db(all_songs, searched_time):
    conn = None
    try:
        conn = get_rds_connection()
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE songs_data")

            insert_sql = """
                INSERT INTO songs_data (video_id, query, searched_time)
                VALUES (%s, %s, %s)
            """

            for item in all_songs:
                cursor.execute(insert_sql, (
                    item.get("video_id", ""),
                    item.get("query", ""),
                    searched_time
                ))

            cursor.execute("""
                INSERT INTO recent_data (video_id, query, searched_time)
                SELECT video_id, query, searched_time
                FROM songs_data
                ON DUPLICATE KEY UPDATE
                    searched_time = VALUES(searched_time)
            """)

        conn.commit()

    except Exception as e:
        logging.error(f"RDS search 업데이트 실패: {e}")

    finally:
        if conn:
            conn.close()


def sleep_until_next_interval():
    time.sleep(SEARCH_API_INTERVAL - time.time() % SEARCH_API_INTERVAL)