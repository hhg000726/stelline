from flask import jsonify
import random, time, logging, string, threading

from .youtube_api import youtube_api_process
from stelline.background_tasks.newOne.clean_expired_sessions import clean_expired_sessions_process
from stelline.config import *
from . import leaderboard

game_sessions = {}
songs = {}
leaderboard.load_leaderboard()
thread = False

# 게임 시작 API
def start_game():
    all_songs = songs["all_songs"]
    if len(all_songs) < 2:
        logging.warning(f"게임을 시작하려 했으나 곡 데이터 부족!")
        return jsonify({"message": "곡 데이터가 부족합니다."}), 400
    
    username = ''.join(random.choice(string.ascii_letters + string.digits + string.digits) for _ in range(8))
    left, right = random.sample(list(all_songs), 2)
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
def submit_choice(data):
    all_songs = songs["all_songs"]
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
            leaderboard.submit_score(username, session_data["score"], elapsed_time)
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
        leaderboard.submit_score(username, session_data["score"], elapsed_time)
        del game_sessions[username]
        logging.info(f"{username}이(가) 오답으로 게임을 종료했습니다. 점수: {session_data['score']}, 현재 유저 수: {len(game_sessions)}")

    return jsonify({"message": message, "username": username, "score": session_data["score"], "left": session_data["left"], "right": session_data["right"], "elapsed_time": elapsed_time})

def get_leaderboard():
    return jsonify(leaderboard.leaderboard)

threading.Thread(target = clean_expired_sessions_process, daemon=True, args = (game_sessions, )).start()
threading.Thread(target = youtube_api_process, daemon=True, args = (songs, )).start()