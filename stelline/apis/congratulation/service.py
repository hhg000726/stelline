import logging
from datetime import datetime, timedelta

from flask import jsonify

from stelline.apis.reports import handle_report_submission
from stelline.database.connection import database_cursor


def fetch_recent_congratulations():
    logging.info("축하 목록 조회 요청")
    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT * FROM song_counts")
            song_counts = cursor.fetchall()
    except Exception:
        logging.exception("DB에서 congratulation 데이터 가져오기 실패")
        return jsonify({"error": "DB에서 congratulation 데이터 가져오기 실패"}), 500

    cutoff = datetime.now() - timedelta(days=1)
    result = [
        {
            "video_id": item.get("video_id"),
            "title": item.get("title"),
            "count": item.get("count"),
            "counted_time": item["counted_time"].isoformat(),
        }
        for item in song_counts
        if item.get("counted_time") and item["counted_time"] >= cutoff
    ]
    logging.info("축하 목록 조회 완료: count=%s", len(result))
    return jsonify(result)


def submit_view_report():
    return handle_report_submission("view_reports", "조회수 알림 제보")
