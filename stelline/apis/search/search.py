from flask import jsonify
import threading, time, logging

from .search_api import *
from stelline.config import *
from stelline.database.db_connection import get_rds_connection

#최근 데이터 불러오기
def processing():
    all_songs, searched_time = load_songs_data()
    now = time.time()
    delay = max(10, searched_time + 6 * 3600 - now)
    formatted_searched_time = time.strftime("%H:%M:%S", time.localtime(searched_time))
    h, remainder = divmod(int(delay), 3600)  # 시, 나머지 초
    m, s = divmod(remainder, 60)
    formatted_delay = f"{h}:{m:02}:{s:02}"
    # 대기 후 API 시작
    logging.info(f"{formatted_searched_time}에 SONGS_DATA_FILE이 있으므로, 첫 검색을 {formatted_delay}만큼 지연..")
    threading.Thread(target=delayed_search_start, daemon=True, args = (delay, )).start()

# 딜레이 시작
def delayed_search_start(delay):
    time.sleep(delay)  # 대기
    logging.info(f"{delay}초 후 API 검색 시작")
    search_api_process()

processing()

# 내 api
def get_not_searched():
    logging.info("곡 정보 불러오는 중..")
    all_songs, searched_time = load_songs_data()
    recent = load_recent_data()
    return jsonify({
        "all_songs": all_songs, 
        "searched_time": searched_time, 
        "recent": recent
    })

def record_search():
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE record_search SET copy_count = copy_count + 1"
            cursor.execute(sql)
            conn.commit()
        logging.info("RDS에서 record_search의 copy_count 업데이트 성공")
    except Exception as e:
        logging.error(f"RDS record_search의 copy_count 업데이트 실패: {e}")
    finally:
        conn.close()

    return '', 204