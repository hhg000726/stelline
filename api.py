from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests, json
from datetime import datetime
from dotenv import load_dotenv
import os, random



#.env 파일 불러오기
load_dotenv()

API_KEY = os.getenv("API_KEY")
PLAYLIST_ID = os.getenv("PLAYLIST_ID")
LEADERBOARD_FILE = os.getenv("LEADERBOARD_FILE", "leaderboard.json")
PORT = int(os.getenv("PORT"))

app = Flask(__name__)
CORS(app)

limiter = Limiter(key_func=get_remote_address)
limiter.init_app(app)

leaderboard = []
game_sessions = {}

def load_leaderboard():
    global leaderboard
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            leaderboard = json.load(f)
            print("리더보드 불러오기 성공!")
    except (FileNotFoundError, json.JSONDecodeError):
        print("리더보드 파일 없음 또는 오류, 새로 생성합니다.")
        leaderboard = []

# 점수 저장 함수
def save_leaderboard():
    with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(leaderboard, f, ensure_ascii=False, indent=4)
    print("💾 리더보드 저장 완료!")

# YouTube 재생목록에서 모든 동영상 가져오기
def get_songs():
    URL = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={PLAYLIST_ID}&maxResults=50&key={API_KEY}"
    
    songs = []
    video_ids = []
    next_page_token = None

    while True:
        response = requests.get(URL + (f"&pageToken={next_page_token}" if next_page_token else ""), timeout=10)
        data = response.json()

        for item in data.get("items", []):
            video_id = item["snippet"]["resourceId"]["videoId"]
            video_ids.append(video_id)
            songs.append({
                "title": item["snippet"]["title"],
                "video_id": video_id
            })

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break  # 다음 페이지가 없으면 종료

    # 동영상 업로드 날짜 가져오기 (50개씩 요청)
    for i in range(0, len(video_ids), 50):
        video_id_str = ",".join(video_ids[i:i+50])
        video_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id_str}&key={API_KEY}"
        video_response = requests.get(video_url).json()

        for item in video_response.get("items", []):
            video_id = item["id"]
            published_at = item["snippet"]["publishedAt"]  # 업로드 날짜

            for song in songs:
                if song["video_id"] == video_id:
                    song["date"] = published_at  # 원본 업로드 날짜 저장

    return songs

all_songs = get_songs()

@app.route("/songs", methods=["GET"])
def songs():
    return jsonify(get_songs())

# 새로운 게임 시작
@app.route("/start_game", methods=["POST"])
@limiter.limit("60 per minute")
def start_game():
    data = request.json
    username = data.get("username", "익명").strip()

    if len(all_songs) < 2:
        return jsonify({"message": "곡 데이터가 부족합니다."}), 400

    left, right = random.sample(all_songs, 2)  # 두 개의 곡 선택
    correct_choice = "left" if left["date"] > right["date"] else "right"

    game_sessions[username] = {
        "left": left,
        "right": right,
        "correct": correct_choice,
        "score": 0,
        "usedSongs": {left["video_id"], right["video_id"]},
        "startTime": datetime.now()
    }

    return jsonify({
        "message": "게임 시작",
        "left": left,
        "right": right,
        "score": 0
    })

# 사용자의 선택을 받아서 점수 계산
@app.route("/submit_choice", methods=["POST"])
def submit_choice():
    data = request.json
    username = data.get("username", "익명").strip()
    if username not in game_sessions:
        return jsonify({"message": "게임을 먼저 시작하세요."}), 400
    choice = data.get("choice", "").strip()
    session_data = game_sessions[username]
    newRight = random.sample(all_songs, 1)[0]
    newLeft = session_data["right"]

    if choice == session_data["correct"]:
        session_data["score"] += 1  # 정답이면 점수 증가
        message = "정답!"
        if len(session_data["usedSongs"]) == len(all_songs):
            message = "끝!"
            submit_score(username)
            return jsonify({"message": message, "score": session_data["score"], "left": newLeft, "right": newRight, "time": (datetime.now() - session_data["startTime"]).total_seconds()})
        while newRight["video_id"] in session_data["usedSongs"]:
            newRight = random.sample(all_songs, 1)[0]
        session_data["usedSongs"].add(newRight["video_id"])
        correct_choice = "left" if newLeft["date"] > newRight["date"] else "right"
        print(correct_choice)
        game_sessions[username] = {
          "left": newLeft,
          "right": newRight,
          "correct": correct_choice,
          "score": session_data["score"],
          "startTime": session_data["startTime"],
          "usedSongs": session_data["usedSongs"]
        }
    else:
        message = "오답!\n" + username + "\n왼쪽: " + session_data["left"]["date"].split("T")[0] + "\n오른쪽: " + session_data["right"]["date"].split("T")[0] + "\n"
        submit_score(username)

    return jsonify({"message": message, "score": session_data["score"], "left": newLeft, "right": newRight})

# 점수 저장
def submit_score(username):
    data = game_sessions[username]

    final_score = data["score"]
    
    time = (datetime.now() - data["startTime"]).total_seconds()
    leaderboard.append({"username": username, "score": final_score, "time": time})
    leaderboard.sort(key=lambda x: (-x["score"], x["time"]))
    leaderboard[:] = leaderboard[:10]  # 상위 10명 유지

    save_leaderboard()  # 파일에 저장

# 리더보드 가져오기 API
@app.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    return jsonify(leaderboard)

load_leaderboard()

if __name__ == "__main__":
    app.run(debug=False)
