from flask import jsonify
import threading, time, json, logging

from . import search_api
from stelline.config import *

songs = {}
recent = {}
search_api.load_song_infos(SONG_INFOS_FILE)
First = True

#최근 데이터 불러오기
def load_recent_data():
    global songs
    global recent
    global First
    if os.path.exists(SONGS_DATA_FILE):  # 파일이 존재하면 불러오기
        try:
            with open(SONGS_DATA_FILE, "r", encoding="utf-8") as f:
                songs = json.load(f)
                logging.info("SONGS_DATA_FILE 로드 완료")
        except (FileNotFoundError, json.JSONDecodeError):
            logging.error("SONGS_DATA_FILE 불러오기 실패")
    if os.path.exists(RECENT_DATA_FILE):  # 파일이 존재하면 불러오고 3시간 대기 후 실행
        try:
            with open(RECENT_DATA_FILE, "r", encoding="utf-8") as f:
                recent = json.load(f)
                logging.info("RECENT_DATA_FILE이 로드 완료")
        except (FileNotFoundError, json.JSONDecodeError):
            logging.error("RECENT_DATA_FILE이 불러오기 실패")

        # 3시간 대기 후 API 시작
        logging.info("RECENT_DATA_FILE이 있으므로, 첫 검색을 3시간 지연..")
        threading.Thread(target=delayed_search_start, daemon=True).start()

    else:  # 파일이 없으면 즉시 실행
        First = False
        logging.info("RECENT_DATA_FILE이 없으므로 즉시 API 검색 시작")
        threading.Thread(target=search_api.search_api_process, daemon=True, args=(songs, recent)).start()

# 딜레이 시작
def delayed_search_start():
    global First
    time.sleep(3 * 3600)  # 3시간 대기
    First = False
    logging.info("3시간 후 API 검색 시작")
    search_api.search_api_process(songs, recent)

# 초기 recent 데이터 로드
load_recent_data()

# 내 api
def get_not_searched():
    global First
    if First:
        songs["searched_time"] = "아직 첫 검색 안됨"
    return jsonify({"all_songs": songs["all_songs"], "searched_time": songs["searched_time"], "recent": recent})