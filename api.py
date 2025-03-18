from flask import Flask, jsonify, request
from flask_cors import CORS
import random, threading, time, logging, string

from config import *
import logging_config, leaderboard, youtube_api

# 로깅 설정 적용
logging_config.setup_logging()

# 앱 생성, CORS 정책
app = Flask(__name__)
CORS(app)

# 게임 관리
game_sessions = {}
leaderboard.load_leaderboard(LEADERBOARD_FILE)
all_songs = youtube_api.get_songs()

# 주기적으로 유튜브 데이터 가져오기
def youtube_api_process():
    global all_songs
    global game_sessions

    while True:
        try:
            new_songs = youtube_api.get_songs()
            if new_songs and new_songs != all_songs:
                all_songs = new_songs
                logging.info("YouTube 데이터 업데이트 완료!")
            else:
                logging.info("새로운 데이터 없음, 기존 데이터를 유지합니다.")
        except Exception as e:
            logging.error(f"YouTube API 업데이트 오류: {e}")
        
        time.sleep(API_CHECK_INTERVAL)

# 주기적으로 세션 정리
def clean_expired_sessions_process():
    while True:
        now = time.time()
        expired_users = [username for username, session in game_sessions.items() if session["last_request"] + 300 <= now]
        
        for user in expired_users:
            del game_sessions[user]
            logging.info(f"{user}의 게임 세션이 만료되어 삭제되었습니다. 현재 유저 수: {len(game_sessions)}")

        time.sleep(SESSION_CHECK_INTERVAL)

# 게임 시작 API
@app.route("/api/newone/start_game", methods=["GET"])
def start_game():
    if len(all_songs) < 2:
        logging.warning(f"게임을 시작하려 했으나 곡 데이터 부족!")
        return jsonify({"message": "곡 데이터가 부족합니다."}), 400
    
    username = ''.join(random.choice(string.ascii_letters + string.digits + string.digits) for _ in range(8))
    left, right = random.sample(all_songs, 2)
    unused_songs = {song["video_id"] for song in all_songs}
    unused_songs.remove(left["video_id"])
    unused_songs.remove(right["video_id"])
    game_sessions[username] = {
        "left": left,
        "right": right,
        "correct": "left" if left["date"] > right["date"] else "right",
        "score": 0,
        "startTime": time.time(),
        "unused_songs": unused_songs,
        "last_request": time.time()
    }

    logging.info(f"{username}이(가) 게임을 시작했습니다.")
    return jsonify({"message": "게임 시작", "username": username, "left": left, "right": right, "score": 0})

# 게임 진행 API
@app.route("/api/newone/submit_choice", methods=["POST"])
def submit_choice():

    data = request.get_json()
    if not data:
        return jsonify({"message": "잘못된 요청: JSON 데이터가 없습니다."}), 400
    
    username = data.get("username", "").strip()
    choice = data.get("choice", "").strip()

    if username not in game_sessions or not username or not choice:
        logging.warning(f"{username}의 잘못된 요청")
        return jsonify({"message": "잘못된 요청: 필수 데이터가 없습니다."}), 400

    session_data = game_sessions[username]
    session_data["last_request"] = time.time()
    elapsed_time = round(time.time() - session_data["startTime"], 1)

    # 정답일 때
    if choice == session_data["correct"]:
        session_data["score"] += 1

        # 끝에 도달한 경우
        if not session_data["unused_songs"]:
            message = "끝!"
            leaderboard.submit_score(username, session_data["score"], elapsed_time, LEADERBOARD_FILE)
            del game_sessions[username]
            logging.info(f"{username}이(가) 게임을 끝까지 했습니다. 점수: {session_data['score']}, 현재 유저 수: {len(game_sessions)}")
            return jsonify({"message": message, "username": username, "score": session_data["score"], "elapsed_time": elapsed_time})
        
        # 끝에 도달하지 않은 경우
        message = "정답!"
        new_right_id = random.choice(list(session_data["unused_songs"]))
        new_right = next(song for song in all_songs if song["video_id"] == new_right_id)
        session_data["left"] = session_data["right"]
        session_data["right"] = new_right
        session_data["correct"] = "left" if session_data["left"]["date"] > session_data["right"]["date"] else "right"
        session_data["unused_songs"].remove(new_right_id)

    # 오답일 때
    else:
        message = "오답!\n코드: " + username + "\n왼쪽: " + session_data["left"]["date"].split("T")[0] + "\n오른쪽: " + session_data["right"]["date"].split("T")[0]
        leaderboard.submit_score(username, session_data["score"], elapsed_time, LEADERBOARD_FILE)
        del game_sessions[username]
        logging.info(f"{username}이(가) 오답으로 게임을 종료했습니다. 점수: {session_data['score']}, 현재 유저 수: {len(game_sessions)}")

    return jsonify({"message": message, "username": username, "score": session_data["score"], "left": session_data["left"], "right": session_data["right"], "elapsed_time": elapsed_time})

@app.route("/api/newone/leaderboard", methods=["GET"])
def get_leaderboard():
    return jsonify(leaderboard.leaderboard)

if __name__ == "__main__":
    threading.Thread(target=youtube_api_process, daemon=True).start()
    threading.Thread(target=clean_expired_sessions_process, daemon=True).start()
    logging.info("서버 시작됨!")
    app.run(host=HOST, port=PORT, debug = DEBUG_MODE, use_reloader = RELOADER_MODE)