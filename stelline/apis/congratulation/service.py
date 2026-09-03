import logging
from datetime import datetime, timedelta

from flask import jsonify, request

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


def _read_token(action):
    """요청에서 FCM 토큰을 꺼낸다. 토큰이 없으면 (None, 400 응답)을 돌려준다.

    세 엔드포인트가 같은 형식을 받고 같은 오류를 내므로 한곳에서 다룬다.
    """
    token = (request.get_json(silent=True) or {}).get("token")
    logging.info("FCM 토큰 %s 요청 수신: token_present=%s", action, bool(token))
    if not token:
        logging.warning("FCM 토큰 %s 요청이 토큰 없이 도착했습니다.", action)
        return None, (jsonify({"error": "Token is missing"}), 400)
    return token, None


def register_token():
    token, missing = _read_token("등록")
    if missing:
        return missing

    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT token FROM fcm_tokens WHERE token = %s", (token,))
            if cursor.fetchone():
                logging.info("Token already exists: token_length=%s", len(token))
            else:
                cursor.execute("INSERT INTO fcm_tokens (token) VALUES (%s)", (token,))
                logging.info("New token registered: token_length=%s", len(token))
        return jsonify({"message": "Token registered"}), 200
    except Exception:
        logging.exception("FCM 토큰 등록 실패")
        return jsonify({"error": "DB insert failed"}), 500


def unregister_token():
    """받은 토큰을 DB에서 지운다. Firebase 쪽 구독 해지는 브라우저가 직접 한다."""
    token, missing = _read_token("삭제")
    if missing:
        return missing

    try:
        with database_cursor() as cursor:
            cursor.execute("DELETE FROM fcm_tokens WHERE token = %s", (token,))
            rows_affected = cursor.rowcount

        if rows_affected > 0:
            logging.info("Token successfully removed from DB.")
            return jsonify({"message": "Token unregistered successfully"}), 200
        logging.warning("Attempted to unregister non-existent token in DB.")
        return jsonify({"message": "Token not found in DB or already unregistered"}), 200
    except Exception:
        logging.exception("FCM 토큰 DB 삭제 실패")
        return jsonify({"error": "Failed to unregister token in DB"}), 500


def check_token():
    token, missing = _read_token("확인")
    if missing:
        return missing

    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT token FROM fcm_tokens WHERE token = %s", (token,))
            is_valid = cursor.fetchone() is not None
        logging.info("FCM 토큰 확인 성공: token_present=%s", is_valid)
        return jsonify({"valid": is_valid}), 200
    except Exception:
        logging.exception("FCM 토큰 확인 실패")
        return jsonify({"error": "DB check failed"}), 500
