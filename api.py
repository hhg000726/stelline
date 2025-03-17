from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO, emit, rooms
from datetime import datetime
from dotenv import load_dotenv
from logging.handlers import TimedRotatingFileHandler
import requests, json, os, random, threading, time, logging, string

# 로그 설정
handler = TimedRotatingFileHandler(
    "app.log", when="midnight", interval=1, backupCount=7
)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler, logging.StreamHandler()]
)

# .env 파일 불러오기
load_dotenv()

API_KEY = os.getenv("API_KEY")
PLAYLIST_ID = os.getenv("PLAYLIST_ID")
LEADERBOARD_FILE = os.getenv("LEADERBOARD_FILE", "leaderboard.json")

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins='*')

limiter = Limiter(key_func=get_remote_address)
limiter.init_app(app)

leaderboard = []
game_sessions = {}

def load_leaderboard():
    """리더보드 파일을 로드"""
    global leaderboard
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            leaderboard = json.load(f)
            logging.info("리더보드 불러오기 성공!")
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("리더보드 파일 없음 또는 오류 발생, 새로 생성합니다.")
        leaderboard = []

def save_leaderboard():
    """리더보드를 저장"""
    try:
        with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(leaderboard, f, ensure_ascii=False, indent=4)
        logging.info("리더보드 저장 완료!")
    except Exception as e:
        logging.error(f"리더보드 저장 중 오류 발생: {e}")

def get_songs():
    """YouTube API에서 재생목록의 곡을 가져옴"""
    logging.info("YouTube API에서 곡 목록을 가져오는 중...")
    URL = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={PLAYLIST_ID}&maxResults=50&key={API_KEY}"
    
    songs = []
    video_ids = []
    next_page_token = None

    try:
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
                break

        logging.info(f"{len(songs)}개의 곡을 가져왔습니다.")

        for i in range(0, len(video_ids), 50):
            video_id_str = ",".join(video_ids[i:i+50])
            video_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id_str}&key={API_KEY}"
            video_response = requests.get(video_url).json()

            for item in video_response.get("items", []):
                video_id = item["id"]
                published_at = item["snippet"]["publishedAt"]

                for song in songs:
                    if song["video_id"] == video_id:
                        song["date"] = published_at

        return songs
    except Exception as e:
        logging.error(f"YouTube API에서 곡을 가져오는 중 오류 발생: {e}")
        return []

all_songs = get_songs()

def songGetter():
    """주기적으로 YouTube 곡 목록 업데이트"""
    while True:
        global all_songs
        try:
            new_songs = get_songs()
            if new_songs:
                all_songs = new_songs
                logging.info("YouTube 데이터 업데이트 완료!")
            else:
                logging.warning("새로운 데이터 없음, 기존 데이터를 유지합니다.")
        except Exception as e:
            logging.error(f"YouTube API 업데이트 오류: {e}")
        time.sleep(60)

@app.route("/api/start_game", methods=["GET"])
@limiter.limit("60 per minute")
def start_game():
    """새로운 게임을 시작"""
    characters = string.ascii_letters + string.digits + string.digits
    username = ''.join(random.choice(characters) for _ in range(8))

    if len(all_songs) < 2:
        logging.warning(f"{username}이(가) 게임을 시작하려 했으나 곡 데이터 부족!")
        return jsonify({"message": "곡 데이터가 부족합니다."}), 400

    left, right = random.sample(all_songs, 2)
    correct_choice = "left" if left["date"] > right["date"] else "right"

    game_sessions[username] = {
        "left": left,
        "right": right,
        "correct": correct_choice,
        "score": 0,
        "usedSongs": {left["video_id"], right["video_id"]},
        "startTime": (datetime.now()).isoformat(),
    }
    logging.info(f"{username}이(가) 게임을 시작했습니다.")
    return jsonify({"message": "게임 시작", "username": username,"left": left, "right": right, "score": 0})

@app.route("/api/submit_choice", methods=["POST"])
def submit_choice():
    """사용자의 선택을 받아 점수를 계산"""
    data = request.json
    username = data.get("username", "익명").strip()

    if username not in game_sessions:
        logging.warning(f"{username}이(가) 게임을 시작하지 않고 제출을 시도함.")
        return jsonify({"message": "게임을 먼저 시작하세요."}), 400

    choice = data.get("choice", "").strip()
    session_data = game_sessions[username]
    newRight = random.sample(all_songs, 1)[0]
    newLeft = session_data["right"]

    if choice == session_data["correct"]:
        session_data["score"] += 1
        message = "정답!"
        if len(session_data["usedSongs"]) == len(all_songs):
            message = "끝!"
            submit_score(username)
            del game_sessions[username]
            logging.info(f"{username}이(가) 게임을 종료했습니다. 점수: {session_data['score']}")
            return jsonify({"message": message, "username": username, "score": session_data["score"]})
        while newRight["video_id"] in session_data["usedSongs"]:
            newRight = random.sample(all_songs, 1)[0]
        session_data["usedSongs"].add(newRight["video_id"])
        correct_choice = "left" if newLeft["date"] > newRight["date"] else "right"
        game_sessions[username] = {
          "left": newLeft,
          "right": newRight,
          "correct": correct_choice,
          "score": session_data["score"],
          "startTime": session_data["startTime"],
          "usedSongs": session_data["usedSongs"],
          "sid": session_data["sid"]
        }
    else:
        message = "오답!\n코드: " + username + "\n왼쪽: " + session_data["left"]["date"].split("T")[0] + "\n오른쪽: " + session_data["right"]["date"].split("T")[0] + "\n"
        submit_score(username)
        del game_sessions[username]

    return jsonify({"message": message, "username": username, "score": session_data["score"], "left": newLeft, "right": newRight})

def submit_score(username):
    """사용자의 점수를 리더보드에 저장"""
    data = game_sessions[username]
    final_score = data["score"]
    elapsed_time = round((datetime.now() - datetime.fromisoformat(data["startTime"])).total_seconds(), 1)

    leaderboard.append({"username": username, "score": final_score, "time": elapsed_time})
    leaderboard.sort(key=lambda x: (-x["score"], x["time"]))
    leaderboard[:] = leaderboard[:10]

    save_leaderboard()
    logging.info(f"{username}이(가) {final_score}점으로 리더보드에 등록됨.")

@app.route("/api/leaderboard", methods=["GET"])
def get_leaderboard():
    return jsonify(leaderboard)

load_leaderboard()

def broadcast_elapsed_time():
    while True:
        current_time = datetime.now()
        for username, session in list(game_sessions.items()):
            start_time = datetime.fromisoformat(session["startTime"])
            elapsed_time = round((current_time - start_time).total_seconds(), 1)
            print(username + " " + session["sid"] + " " + str(elapsed_time))
            room_list = rooms()
            logging.info(f"✅ 현재 존재하는 WebSocket Rooms: {room_list}")
            socketio.emit("elapsed_time", {"elapsed_time": elapsed_time}, room=session["sid"])  # 개별 유저에게 전송
        time.sleep(0.1)

@socketio.on("join_game")
def handle_join_game(data):
    """클라이언트가 WebSocket을 통해 게임방에 참가"""
    username = data.get("username")
    if username in game_sessions:
        sid = request.sid
        game_sessions[username]["sid"] = sid
        logging.info(f"{username}이(가) {sid} 로에 입장했습니다.")
        room_list = rooms()
        logging.info(f"✅ 현재 존재하는 WebSocket Rooms: {room_list}")
    else:
        emit("error", {"message": "게임 세션이 존재하지 않습니다."})

@socketio.on("leave_game")
def handle_leave_game(data):
    """클라이언트가 WebSocket을 통해 게임방에서 퇴장"""
    username = data.get("username")
    if username in game_sessions:
        sid = game_sessions[username]["sid"]
        logging.info(f"{username}이(가) {sid}로 퇴장했습니다.")
        room_list = rooms()
        logging.info(f"✅ 현재 존재하는 WebSocket Rooms: {room_list}")
    else:
        emit("error", {"message": "게임 세션이 존재하지 않습니다."})

@socketio.on("connect")
def handle_connect():
    """새로운 사용자가 WebSocket에 연결될 때 실행"""
    sid = request.sid
    logging.info(f"새로운 WebSocket 연결: {sid}")
     
@socketio.on("disconnect")
def handle_disconnect():
    """클라이언트가 브라우저를 닫거나 네트워크가 끊겼을 때 실행됨"""
    sid = request.sid  # 현재 사용자의 세션 ID

    # game_sessions에서 해당 사용자를 찾기
    username_to_remove = None
    for username, session in game_sessions.items():
        if session.get("sid") == sid:
            username_to_remove = username
            break

    if username_to_remove:
        del game_sessions[username_to_remove]
        logging.info(f"{username_to_remove}이(가) 브라우저 종료로 게임에서 제거됨.")
        room_list = rooms()
        logging.info(f"✅ 현재 존재하는 WebSocket Rooms: {room_list}")

if __name__ == "__main__":
    threading.Thread(target=songGetter, daemon=True).start()
    threading.Thread(target=broadcast_elapsed_time, daemon=True).start()
    logging.info("서버 시작됨!")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)