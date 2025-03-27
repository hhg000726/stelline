import json, logging

from stelline.config import *
from stelline.database.db_connection import get_rds_connection

def record_main():
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE record_main SET copy_count = copy_count + 1"
            cursor.execute(sql)
            conn.commit()
        logging.info("RDS에서 record_main copy_count 업데이트 성공")
    except Exception as e:
        logging.error(f"RDS record_main copy_count 업데이트 실패: {e}")
    finally:
        conn.close()

    return '', 204