from dotenv import load_dotenv
import os

# .env 파일 불러오기
load_dotenv()

API_KEY = os.getenv("API_KEY")
PLAYLIST_ID = os.getenv("PLAYLIST_ID")
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY").split(',')
TEMP_API_KEY = os.getenv("TEMP_API_KEY")

# 관리자 아이디
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")

# RDS
RDS_HOST = os.getenv("RDS_HOST")
RDS_USER = os.getenv("RDS_USER")
RDS_PASSWORD = os.getenv("RDS_PASSWORD")
RDS_DB = os.getenv("RDS_DB")

# 서버 설정
HOST = "0.0.0.0"
PORT = 5000
DEBUG_MODE = False
RELOADER_MODE = False

# 게임 설정
API_CHECK_INTERVAL = 300  # 유튜브 API 업데이트 및 세션 정리 주기 (초)
SESSION_CHECK_INTERVAL = 30 # 세션 정리 주기 (초)
SEARCH_API_INTERVAL = 6 * 3600

# 유튜브 API 설정
MAX_RESULTS = 50

#네이버 지도 API 설정
NCP_CLIENT_ID = os.getenv("NCP_CLIENT_ID")
NCP_CLIENT_SECRET = os.getenv("NCP_CLIENT_SECRET")

# 알림 설정
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
PROJECT_ID = os.getenv("PROJECT_ID")