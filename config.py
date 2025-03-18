from dotenv import load_dotenv
import os

# .env 파일 불러오기
load_dotenv()

API_KEY = os.getenv("API_KEY")
PLAYLIST_ID = os.getenv("PLAYLIST_ID")
LEADERBOARD_FILE = os.getenv("LEADERBOARD_FILE", "leaderboard.json")

# 서버 설정
HOST = "0.0.0.0"
PORT = 5000
DEBUG_MODE = False
RELOADER_MODE = False

# 게임 설정
API_CHECK_INTERVAL = 300  # 유튜브 API 업데이트 및 세션 정리 주기 (초)
SESSION_CHECK_INTERVAL = 300 # 세션 정리 주기 (초)

# 유튜브 API 설정
MAX_RESULTS = 50