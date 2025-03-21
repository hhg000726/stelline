import json, logging, time, requests, random
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

def search_api(recent):
    logging.info(f"검색 시작")
    url = "https://www.googleapis.com/youtube/v3/search"
    not_searched = []
    search_targets = [
        {"query": q, "video_id": v[0]}
        for q, v in recent.items()
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
            "fields": "items(id(videoId))",
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
def search_api_process(songs, recent):
    logging.info("주기적 검색 시작됨")
    search_api_interval = 6 * 3600
    while True:
        try:
            new_songs = search_api(recent)
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