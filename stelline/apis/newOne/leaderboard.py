import json, logging

from stelline.config import *
from stelline.database.db_connection import get_rds_connection

def load_leaderboard():
    try:
        conn = get_rds_connection()
        with conn.cursor() as cursor:
            sql = "SELECT * FROM leaderboard"
            cursor.execute(sql)
            leaderboard = cursor.fetchall()
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error("리더보드 불러오기 오류 발생.")
        leaderboard = []
    return leaderboard

# 점수 기록
def submit_score(username, score, elapsed_time):
    data = {"username": username, "score": score, "elapsed_time": elapsed_time}
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM leaderboard"
            cursor.execute(sql)
            leaderboard = cursor.fetchall()
            try:
                leaderboard.append(data)
            except Exception as e:
                logging.info(e)
            leaderboard.sort(key=lambda x: (-x["score"], x["elapsed_time"]))
            leaderboard[:] = leaderboard[:10]

            sql = "TRUNCATE TABLE leaderboard"
            cursor.execute(sql)

            for item in leaderboard:
                sql = """
                    INSERT INTO leaderboard (username, score, elapsed_time)
                    VALUES (%s, %s, %s)
                """
                cursor.execute(sql, (item["username"], item["score"], item["elapsed_time"]))
            sql = "UPDATE record_search SET total_plays = total_plays + 1"
            cursor.execute(sql)
            sql = """
                UPDATE record_search SET total_play_time = total_play_time + %s
            """
            cursor.execute(sql, (elapsed_time,))
            conn.commit()
        logging.info("RDS에서 leaderboard, record_search 업데이트 성공")
    except Exception as e:
        logging.error(f"RDS leaderboard, record_search 업데이트 실패: {e}")
    finally:
        conn.close()
    