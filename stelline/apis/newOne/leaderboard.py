import json, logging, os

leaderboard = []

def load_leaderboard(LEADERBOARD_FILE):
    global leaderboard
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            leaderboard = json.load(f)
            logging.info("리더보드 불러오기 성공!")
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error("리더보드 파일 없음 또는 오류 발생, 새로 생성합니다.")
        leaderboard = []

def save_leaderboard(LEADERBOARD_FILE):
    try:
        temp_file = LEADERBOARD_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(leaderboard, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, LEADERBOARD_FILE)
        logging.info("리더보드 저장 완료!")
    except Exception as e:
        logging.error(f"리더보드 저장 중 오류 발생: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

# 점수 기록
def submit_score(username, score, elapsed_time, LEADERBOARD_FILE):
    leaderboard.append({"username": username, "score": score, "time": elapsed_time})
    leaderboard.sort(key=lambda x: (-x["score"], x["time"]))
    leaderboard[:] = leaderboard[:10]

    save_leaderboard(LEADERBOARD_FILE)
    logging.info(f"{username}이(가) {score}점을 기록함.")