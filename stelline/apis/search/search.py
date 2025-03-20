from flask import jsonify
import threading, time, json, logging

from . import search_api
from stelline.config import *

songs = {}
recent = {}
search_api.load_song_infos(SONG_INFOS_FILE)

#최근 데이터 불러오기
def load_recent_data():
    global songs
    global recent
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
        logging.info("RECENT_DATA_FILE이 없으므로 즉시 API 검색 시작")
        threading.Thread(target=search_api.search_api_process, daemon=True, args=(songs, recent)).start()

# 딜레이 시작
def delayed_search_start():
    time.sleep(3 * 3600)  # 3시간 대기
    logging.info("3시간 후 API 검색 시작")
    search_api.search_api_process(songs, recent)

# 초기 recent 데이터 로드
load_recent_data()

# 내 api
def get_not_searched():
    return jsonify({"all_songs": songs["all_songs"], "searched_time": songs["searched_time"], "recent": recent})

# record 로드
def load_record():
    if os.path.exists(RECORD_FILE):
        try:
            with open(RECORD_FILE, "r", encoding="utf-8") as f:
                logging.info("record.json 불러오기 성공")
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logging.error("record.json 불러오기 실패. 기본값으로 설정")
    return {"total_plays": 0, "total_play_time": 0.0, "copy_count": 0}

# record 저장
def save_record(record):
    try:
        temp_file = RECORD_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, RECORD_FILE)
        logging.info(f"record.json 업데이트 완료! 총 복사 수: {record['copy_count']}")
    except Exception as e:
        logging.error(f"record.json 저장 오류: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

def record_search():
    record = load_record()
    record["copy_count"] += 1  # 플레이 횟수 증가
    save_record(record)  # 저장
    
    return '', 204