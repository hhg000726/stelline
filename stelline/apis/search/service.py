import logging

from flask import jsonify

from stelline.apis.reports import handle_report_submission
from stelline.database.connection import database_cursor
from .tasks import (
    fetch_recent_data_from_db,
    fetch_song_infos_from_db,
    fetch_songs_data_from_db,
)


def get_not_searched():
    logging.info("미검색곡 조회 요청")
    all_songs, searched_time = fetch_songs_data_from_db()
    recent = fetch_recent_data_from_db()
    return jsonify({
        "all_songs": all_songs,
        "searched_time": searched_time,
        "recent": recent,
    })


def get_song_infos():
    logging.info("곡 메타 정보 조회 요청")
    return jsonify(fetch_song_infos_from_db())


def record_search():
    logging.info("검색 기록 카운트 증가 요청")
    try:
        with database_cursor() as cursor:
            cursor.execute("UPDATE record_search SET copy_count = copy_count + 1")
    except Exception:
        logging.exception("RDS record_search의 copy_count 업데이트 실패")

    return '', 204


def submit_song_report():
    return handle_report_submission("song_reports", "노래 제보")
