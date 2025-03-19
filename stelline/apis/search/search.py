from flask import jsonify
import threading, time, json, logging

from . import search_api
from stelline.config import *

songs = {}
recent = {}
search_api.load_song_infos(SONG_INFOS_FILE)

#최근 데이터 불러오기
def load_recent_data():
    global recent
    if os.path.exists(RECENT_DATA_FILE):  # 파일이 존재하면 불러오고 3시간 대기 후 실행
        try:
            with open(RECENT_DATA_FILE, "r", encoding="utf-8") as f:
                recent = json.load(f)
                songs["all_songs"] = []
                songs["searched_time"] = "아직 첫 검색 안됨"
                for i in recent:
                    songs["all_songs"].append({"query": i, "video_id": recent[i][0]})

                logging.info("recent_data.json 로드 완료")
        except (FileNotFoundError, json.JSONDecodeError):
            logging.error("recent_data.json 불러오기 실패")

        # 3시간 대기 후 API 시작
        logging.info("recent_data.json이 있으므로, 첫 검색을 3시간 지연..")
        threading.Thread(target=delayed_search_start, daemon=True).start()

    else:  # 파일이 없으면 즉시 실행
        logging.info("recent_data.json이 없으므로 즉시 API 검색 시작")
        threading.Thread(target=search_api.search_api_process, daemon=True, args=(songs,)).start()

# 딜레이 시작
def delayed_search_start():
    time.sleep(3 * 3600)  # 3시간 대기
    logging.info("3시간 후 API 검색 시작")
    search_api.search_api_process(songs)

# 초기 recent 데이터 로드
load_recent_data()

# 내 api
def get_not_searched():
    new_songs = songs["all_songs"]
    now = songs["searched_time"]
    for song in new_songs:
        recent[song["query"]] = [song["video_id"], now]
    for song in list(recent.keys()):
        if recent[song][1] + 604800 < time.time():
            del recent[song]
    save_recent_data()
    return jsonify({"all_songs": new_songs, "searched_time": now, "recent": recent})

# recent 데이터를 recent_data.json에 저장
def save_recent_data():
    try:
        with open(RECENT_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(recent, f, ensure_ascii=False, indent=4)
        print("recent_data.json 저장 완료")
    except Exception as e:
        print(f"recent_data.json 저장 오류: {e}")