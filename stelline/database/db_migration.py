import logging, json

from .db_connection import get_rds_connection
from stelline.config import *

def migrate_json_to_rds_song_infos():
    """
    JSON 파일에 들어있는 song_infos 데이터를 RDS에 한 번 저장해주는 함수.
    """
    try:
        with open(SONG_INFOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error(f"{SONG_INFOS_FILE} 정보 JSON 불러오기 실패")
        return
    
    logging.info("JSON 데이터 -> RDS 마이그레이션 시작...")
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                CREATE TABLE IF NOT EXISTS song_infos (
                    video_id VARCHAR(100),
                    query VARCHAR(100)
                );
                """
            cursor.execute(sql)
            sql = """
                TRUNCATE TABLE song_infos;
                """
            cursor.execute(sql)
            for item in data:
                video_id = item.get("video_id", "")
                query = item.get("query", "")
                logging.info(f"👉 삽입 시도: {video_id}, {query}")  
                sql = """
                INSERT INTO song_infos (video_id, query)
                VALUES (%s, %s)
                """
                cursor.execute(sql, (video_id, query))
        conn.commit()
        logging.info("JSON 데이터 -> RDS 마이그레이션 완료")
    finally:
        conn.close()

def migrate_json_to_rds_record_main():
    """
    JSON 파일에 들어있는 song_infos 데이터를 RDS에 한 번 저장해주는 함수.
    """
    try:
        with open(RECORD_MAIN, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error(f"{RECORD_MAIN} 정보 JSON 불러오기 실패")
        return
    
    logging.info("JSON 데이터 -> RDS 마이그레이션 시작...")
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                CREATE TABLE IF NOT EXISTS record_main (
                    copy_count INT
                );
                """
            cursor.execute(sql)
            sql = """
                TRUNCATE TABLE record_main;
                """
            cursor.execute(sql)
            copy_count = data.get("copy_count", "")
            sql = """
            INSERT INTO record_main (copy_count)
            VALUES (%s)
            """
            cursor.execute(sql, (copy_count))
        conn.commit()
        logging.info("JSON 데이터 -> RDS 마이그레이션 완료")
    finally:
        conn.close()


def migrate_json_to_rds_record_search():
    """
    JSON 파일에 들어있는 song_infos 데이터를 RDS에 한 번 저장해주는 함수.
    """
    try:
        with open(RECORD_SEARCH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error(f"{RECORD_SEARCH} 정보 JSON 불러오기 실패")
        return
    
    logging.info("JSON 데이터 -> RDS 마이그레이션 시작...")
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                CREATE TABLE IF NOT EXISTS record_search (
                    total_plays INT,
                    total_play_time DOUBLE,
                    copy_count INT
                );
                """
            cursor.execute(sql)
            sql = """
                TRUNCATE TABLE record_search;
                """
            cursor.execute(sql)
            total_plays = data.get("total_plays", "")
            total_play_time = data.get("total_play_time", "")
            copy_count = data.get("copy_count", "")
            sql = """
            INSERT INTO record_search (total_plays, total_play_time, copy_count)
            VALUES (%s, %s, %s)
            """
            cursor.execute(sql, (total_plays, total_play_time, copy_count))
        conn.commit()
        logging.info("JSON 데이터 -> RDS 마이그레이션 완료")
    finally:
        conn.close()

def migrate_json_to_rds_songs_data():
    """
    JSON 파일에 들어있는 song_infos 데이터를 RDS에 한 번 저장해주는 함수.
    """
    try:
        with open(SONGS_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error(f"{SONGS_DATA_FILE} 정보 JSON 불러오기 실패")
        return
    
    logging.info("JSON 데이터 -> RDS 마이그레이션 시작...")
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                CREATE TABLE IF NOT EXISTS songs_data (
                    video_id VARCHAR(100),
                    query VARCHAR(100),
                    searched_time DOUBLE
                );
                """
            cursor.execute(sql)
            sql = """
                TRUNCATE TABLE songs_data;
                """
            cursor.execute(sql)
            songs = data.get("all_songs", [])
            searched_time = data.get("searched_time", 0)
            for item in songs:
                video_id = item.get("video_id", "")
                query = item.get("query", "")
                cursor.execute("""
                    INSERT INTO songs_data (video_id, query, searched_time)
                    VALUES (%s, %s, %s)
                """, (video_id, query, searched_time))
        conn.commit()
        logging.info("JSON 데이터 -> RDS 마이그레이션 완료")
    finally:
        conn.close()

def migrate_json_to_rds_targets():
    """
    JSON 파일에 들어있는 song_infos 데이터를 RDS에 한 번 저장해주는 함수.
    """
    try:
        with open(TARGETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error(f"{TARGETS_FILE} 정보 JSON 불러오기 실패")
        return
    
    logging.info("JSON 데이터 -> RDS 마이그레이션 시작...")
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                CREATE TABLE IF NOT EXISTS targets (
                    name VARCHAR(100),
                    title VARCHAR(100),
                    url_number INT
                );
                """
            cursor.execute(sql)
            sql = """
                TRUNCATE TABLE targets;
                """
            cursor.execute(sql)
            for item in data:
                name = item.get("name", "")
                title = item.get("title", "")
                url_number = item.get("url_number", "")
                sql = """
                INSERT INTO targets (name, title, url_number)
                VALUES (%s, %s, %s)
                """
                cursor.execute(sql, (name, title, url_number))
        conn.commit()
        logging.info("JSON 데이터 -> RDS 마이그레이션 완료")
    finally:
        conn.close()

def migrate_json_to_rds_leaderboard():
    """
    JSON 파일에 들어있는 song_infos 데이터를 RDS에 한 번 저장해주는 함수.
    """
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error(f"{LEADERBOARD_FILE} 정보 JSON 불러오기 실패")
        return
    
    logging.info("JSON 데이터 -> RDS 마이그레이션 시작...")
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                CREATE TABLE IF NOT EXISTS leaderboard (
                    username VARCHAR(100),
                    score INT,
                    time DOUBLE
                );
                """
            cursor.execute(sql)
            sql = """
                TRUNCATE TABLE leaderboard;
                """
            cursor.execute(sql)
            for item in data:
                username = item.get("username", "")
                score = item.get("score", "")
                time = item.get("time", "")
                sql = """
                INSERT INTO leaderboard (username, score, time)
                VALUES (%s, %s, %s)
                """
                cursor.execute(sql, (username, score, time))
        conn.commit()
        logging.info("JSON 데이터 -> RDS 마이그레이션 완료")
    finally:
        conn.close()

def migrate_json_to_rds_recent_data():
    """
    JSON 파일에 들어있는 song_infos 데이터를 RDS에 한 번 저장해주는 함수.
    """
    try:
        with open(RECENT_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error(f"{RECENT_DATA_FILE} 정보 JSON 불러오기 실패")
        return
    
    logging.info("JSON 데이터 -> RDS 마이그레이션 시작...")
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                CREATE TABLE IF NOT EXISTS recent_data (
                    query VARCHAR(100),
                    video_id VARCHAR(100),
                    time DOUBLE
                );
                """
            cursor.execute(sql)
            sql = """
                TRUNCATE TABLE recent_data;
                """
            cursor.execute(sql)
            for query, value in data.items():
                if not isinstance(value, list) or len(value) != 2:
                    logging.warning(f"값 형식 이상 → query: {query}, value: {value}")
                    continue
                video_id, time = value
                sql = """
                INSERT INTO recent_data (query, video_id, time)
                VALUES (%s, %s, %s)
                """
                cursor.execute(sql, (query, video_id, time))
        conn.commit()
        logging.info("JSON 데이터 -> RDS 마이그레이션 완료")
    finally:
        conn.close()

def migrate_json_to_rds():
    migrate_json_to_rds_record_main()
    migrate_json_to_rds_record_search()
    migrate_json_to_rds_songs_data()
    migrate_json_to_rds_song_infos()
    migrate_json_to_rds_targets()
    migrate_json_to_rds_leaderboard()
    migrate_json_to_rds_recent_data()

def check_migration():
    tables = [
        "song_infos",
        "record_main",
        "record_search",
        "songs_data",
        "targets",
        "leaderboard",
        "recent_data"
    ]
    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables_list = cursor.fetchall()
            logging.info(f"현재 존재하는 테이블: {[row[0] for row in tables_list]}")
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    logging.info(f"{table}: {count}건")
                except Exception as e:
                    logging.warning(f"{table} 확인 실패: {e}")
    finally:
        conn.close()