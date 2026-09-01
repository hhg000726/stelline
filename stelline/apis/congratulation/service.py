import logging
from datetime import datetime, timedelta

from flask import jsonify

from stelline.apis.reports import handle_report_submission
from stelline.database.connection import database_cursor


# 최근 하루 안에 달성한 곡만 화면에 띄운다. 걸러 낼 행을 DB에서 미리 잘라 내면
# 통째로 받아 와 파이썬에서 버리는 것보다 전송·파싱할 데이터가 줄어든다.
RECENT_QUERY = """
    SELECT video_id, title, count, counted_time
      FROM song_counts
     WHERE counted_time >= %s
"""


def fetch_recent_congratulations():
    logging.info("축하 목록 조회 요청")
    cutoff = datetime.now() - timedelta(days=1)
    try:
        with database_cursor() as cursor:
            cursor.execute(RECENT_QUERY, (cutoff,))
            song_counts = cursor.fetchall()
    except Exception:
        logging.exception("DB에서 congratulation 데이터 가져오기 실패")
        return jsonify({"error": "DB에서 congratulation 데이터 가져오기 실패"}), 500

    result = [
        {
            "video_id": item["video_id"],
            "title": item["title"],
            "count": item["count"],
            "counted_time": item["counted_time"].isoformat(),
        }
        for item in song_counts
    ]
    logging.info("축하 목록 조회 완료: count=%s", len(result))
    return jsonify(result)


def submit_view_report():
    return handle_report_submission("view_reports", "조회수 알림 제보")
