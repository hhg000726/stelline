from datetime import datetime, timedelta
import logging
from flask import jsonify

from stelline.database.connection import get_connection

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
