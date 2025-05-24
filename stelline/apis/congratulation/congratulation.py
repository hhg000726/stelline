import datetime
import logging
from flask import jsonify

from stelline.config import *
from stelline.database.db_connection import get_rds_connection

def congratulations():
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            result = []
            sql = "SELECT * FROM song_counts"
            cursor.execute(sql)
            song_counts = cursor.fetchall()
            for item in song_counts:
                if item.get("counted_time") >= datetime.now() - datetime.timedelta(days=1):
                    result.append(item)
    except Exception as e:
        logging.error(f"DB에서 congratulation 데이터 가져오기 실패: {e}")
        return jsonify({"error": "DB에서 congratulation 데이터 가져오기 실패"}), 500
    finally:
        conn.close()
        
    return jsonify(result)