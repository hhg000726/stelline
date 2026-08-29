"""환경별 설정. 개발 환경은 .env.development, 운영은 .env를 사용한다."""

import os
from pathlib import Path

from dotenv import load_dotenv

APP_ENV = os.getenv("APP_ENV", "production").lower()
if APP_ENV not in {"development", "production"}:
    raise RuntimeError("APP_ENV는 development 또는 production이어야 합니다.")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / (".env.development" if APP_ENV == "development" else ".env")
load_dotenv(ENV_FILE)

API_KEY = os.getenv("API_KEY")
PLAYLIST_ID = os.getenv("PLAYLIST_ID")
SEARCH_API_KEY = [key for key in os.getenv("SEARCH_API_KEY", "").split(",") if key]
TEMP_API_KEY = os.getenv("TEMP_API_KEY")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY")
ADMIN_HTML_SNAPSHOT_PATH = os.getenv("ADMIN_HTML_SNAPSHOT_PATH", "")

# 이름은 기존 코드와 호환되지만 development에서는 Docker의 별도 DB를 가리킨다.
RDS_HOST = os.getenv("RDS_HOST")
RDS_PORT = int(os.getenv("RDS_PORT", "3306"))
RDS_USER = os.getenv("RDS_USER")
RDS_PASSWORD = os.getenv("RDS_PASSWORD")
RDS_DB = os.getenv("RDS_DB")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))
DEBUG_MODE = APP_ENV == "development"
RELOADER_MODE = DEBUG_MODE
AUTO_CREATE_SCHEMA = os.getenv("AUTO_CREATE_SCHEMA", "false").lower() == "true"
START_BACKGROUND_TASKS = os.getenv("START_BACKGROUND_TASKS", "true").lower() == "true"

API_CHECK_INTERVAL = 300
SEARCH_API_INTERVAL = 6 * 3600
MAX_RESULTS = 50

NCP_CLIENT_ID = os.getenv("NCP_CLIENT_ID")
NCP_CLIENT_SECRET = os.getenv("NCP_CLIENT_SECRET")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
PROJECT_ID = os.getenv("PROJECT_ID")
