import json, logging, os

from stelline.config import *

leaderboard = []

def load_leaderboard():
    global leaderboard
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            leaderboard = json.load(f)
            logging.info("리더보드 불러오기 성공!")
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error("리더보드 파일 없음 또는 오류 발생, 새로 생성합니다.")
        leaderboard = []

def save_leaderboard():
    try:
        temp_file = LEADERBOARD_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(leaderboard, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, LEADERBOARD_FILE)
    except Exception as e:
        logging.error(f"리더보드 저장 중 오류 발생: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

# record 로드
def load_record():
    if os.path.exists(RECORD_FILE):
        try:
            with open(RECORD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logging.error("record.json 불러오기 실패. 기본값으로 설정")
    return {"total_plays": 0, "total_play_time": 0.0, "copy_count": 0}

# record 저장
def save_record(record):
    try:
        temp_file = RECORD_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, RECORD_FILE)
    except Exception as e:
        logging.error(f"record.json 저장 오류: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

# 점수 기록
def submit_score(username, score, elapsed_time):
    leaderboard.append({"username": username, "score": score, "time": elapsed_time})
    leaderboard.sort(key=lambda x: (-x["score"], x["time"]))
    leaderboard[:] = leaderboard[:10]

    save_leaderboard()
    logging.info(f"{username}이(가) {score}점을 기록함.")

    record = load_record()
    record["total_plays"] += 1  # 플레이 횟수 증가
    record["total_play_time"] += elapsed_time  # 플레이 시간 증가
    save_record(record)  # 저장
    