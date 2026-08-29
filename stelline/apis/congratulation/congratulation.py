from datetime import datetime, timedelta
import logging
from flask import jsonify, request

from stelline.database.connection import get_connection
from stelline.apis.turnstile import verify_turnstile

def congratulations():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            result = []
            sql = "SELECT * FROM song_counts"
            cursor.execute(sql)
            song_counts = cursor.fetchall()
            for item in song_counts:
                counted = item.get("counted_time")
                if not counted:
                    continue
                # DB에서 받은 datetime 객체를 비교 후, JSON 직렬화 가능한 형태로 변환
                if counted >= datetime.now() - timedelta(days=1):
                    result.append({
                        "video_id": item.get("video_id"),
                        "title": item.get("title"),
                        "count": item.get("count"),
                        "counted_time": counted.isoformat()
                    })
    except Exception as e:
        logging.error(f"DB에서 congratulation 데이터 가져오기 실패: {e}")
        return jsonify({"error": "DB에서 congratulation 데이터 가져오기 실패"}), 500
    finally:
        conn.close()
        
    return jsonify(result)


def submit_view_report():
    payload = request.get_json(silent=True) or {}
    if not verify_turnstile(payload.get("captcha_token")):
        return jsonify({"error": "캡차 인증에 실패했습니다. 다시 시도하세요."}), 400
    raw_content = payload.get("content", "")
    content = raw_content.strip() if isinstance(raw_content, str) else ""
    if not content:
        return jsonify({"error": "제보 내용을 입력하세요."}), 400
    if len(content) > 2000:
        return jsonify({"error": "제보 내용은 2000자 이내로 입력하세요."}), 400

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO view_reports (content) VALUES (%s)", (content,))
        conn.commit()
    except Exception as error:
        conn.rollback()
        logging.error("조회수 알림 제보 저장 실패: %s", error)
        return jsonify({"error": "제보를 저장하지 못했습니다."}), 500
    finally:
        conn.close()

    return jsonify({"message": "제보가 접수되었습니다."}), 201
