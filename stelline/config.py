"""환경별 설정. 개발 환경은 .env.development, 운영은 .env를 사용한다."""

import logging
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
# 관리자 세션 쿠키를 https 에서만 보낸다. 개발 서버는 http 라 기본으로 끈다.
SESSION_COOKIE_SECURE = os.getenv(
    "SESSION_COOKIE_SECURE", "false" if APP_ENV == "development" else "true"
).lower() == "true"

API_CHECK_INTERVAL = 300
# 검색 점검은 8시간마다(한국 시간 01·09·17시, UTC 기준 0·8·16시) 하루 세 번 돈다.
# YouTube 할당량(프로젝트당 하루 10,000, 검색 한 번 100)은 태평양 시간 자정에 다시 차는데,
# 8시간 간격이면 서머타임과 상관없이 할당 하루마다 정확히 세 회차가 들어간다.
# 예전 6시간(네 회차 × 25회)은 할당량을 꽉 채워, 같은 프로젝트의 다른 사용분만큼
# 마지막 회차(15시)가 늘 429 로 끊겼다.
SEARCH_API_INTERVAL = 8 * 3600
MAX_RESULTS = 50

NCP_CLIENT_ID = os.getenv("NCP_CLIENT_ID")
NCP_CLIENT_SECRET = os.getenv("NCP_CLIENT_SECRET")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
PROJECT_ID = os.getenv("PROJECT_ID")

logging.getLogger(__name__).info(
    "환경 설정 로드 완료: APP_ENV=%s, DEBUG_MODE=%s, START_BACKGROUND_TASKS=%s, AUTO_CREATE_SCHEMA=%s",
    APP_ENV,
    DEBUG_MODE,
    START_BACKGROUND_TASKS,
    AUTO_CREATE_SCHEMA,
)
