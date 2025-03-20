import json, logging, time, requests
from stelline.config import *

song_infos = []

def load_song_infos(SONG_INFOS_FILE):
    logging.info("곡 정보 불러오는 중..")
    global song_infos
    try:
        global song_infos
        with open(SONG_INFOS_FILE, "r", encoding="utf-8") as f:
            song_infos = json.load(f)
            logging.info("곡 정보 불러오기 성공")
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error("곡 정보 불러오기 실패")
        exit(1)

def search_api():
    batch_size = len(song_infos) // len(SEARCH_API_KEYS) + 1
    logging.info(f"검색 시작, 곡수={len(song_infos)} batch_size={batch_size}")
    url = "https://www.googleapis.com/youtube/v3/search"
    not_searched = []
    for i in range(0, len(song_infos), batch_size):
        logging.info(f"{i // batch_size}번째 배치 실행중..")
        for song_info in song_infos[i:i + batch_size]:
            query = song_info["query"]
            video_id = song_info["video_id"]
            
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 3,
                "key": SEARCH_API_KEYS[i // batch_size]
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
def search_api_process(songs, recent):
    logging.info("주기적 검색 시작됨")
    search_api_interval = 3 * 3600
    while True:
        try:
            new_songs = search_api()
            songs.clear()
            songs.update(new_songs)

            now = songs["searched_time"]
            for song in songs["all_songs"]:
                recent[song["query"]] = [song["video_id"], now]
            for song in list(recent.keys()):
                if recent[song][1] + 604800 < time.time():
                    del recent[song]
            save_data(songs, recent)

            logging.info("검색 데이터 업데이트 완료!")
        except Exception as e:
            logging.error(f"검색 업데이트 오류: {e}")
        
        time.sleep(search_api_interval)

# songs, recent 데이터를 저장
def save_data(songs, recent):
    try:
        songs_temp_file = SONGS_DATA_FILE + ".tmp"
        with open(songs_temp_file, "w", encoding="utf-8") as f:
            json.dump(songs, f, ensure_ascii=False, indent=4)
        os.replace(songs_temp_file, SONGS_DATA_FILE)
        logging.info("SONGS_DATA_FILE 저장 완료")
    except Exception as e:
        logging.error(f"SONGS_DATA_FILE 저장 오류: {e}")
        if os.path.exists(songs_temp_file):
            os.remove(songs_temp_file)
    try:
        recent_temp_file = RECENT_DATA_FILE + ".tmp"
        with open(recent_temp_file, "w", encoding="utf-8") as f:
            json.dump(recent, f, ensure_ascii=False, indent=4)
        os.replace(recent_temp_file, RECENT_DATA_FILE)
        logging.info("RECENT_DATA_FILE 저장 완료")
    except Exception as e:
        logging.error(f"RECENT_DATA_FILE 저장 오류: {e}")
        if os.path.exists(recent_temp_file):
            os.remove(recent_temp_file)