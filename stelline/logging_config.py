import logging
import os
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_ROTATION_TIME = "midnight"
LOG_INTERVAL = 1
LOG_BACKUP_DAYS = 7

# 수준별로 파일을 나눈다. 각 파일에는 그 수준 이상만 쌓인다.
LOG_FILES = (
    ("app_info.log", logging.INFO),
    ("app_warning.log", logging.WARNING),
    ("app_error.log", logging.ERROR),
)

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")


def create_log_handler(filename, level):
    # 인코딩을 정하지 않으면 OS 기본값(윈도우는 cp949)을 쓴다. 로그에 한글 밖의
    # 문자가 섞이면 그 줄이 통째로 사라지므로 utf-8로 못 박는다.
    # delay=True: 실제로 기록할 때까지 파일을 열지 않는다.
    handler = TimedRotatingFileHandler(
        f"{LOG_DIR}/{filename}",
        when=LOG_ROTATION_TIME,
        interval=LOG_INTERVAL,
        backupCount=LOG_BACKUP_DAYS,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(formatter)
    handler.setLevel(level)
    return handler


def setup_logging():
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.propagate = False
    for filename, level in LOG_FILES:
        logger.addHandler(create_log_handler(filename, level))
    logger.setLevel(logging.INFO)
    logger.info("로그 설정이 초기화되었습니다. 로그 디렉터리: %s", LOG_DIR)
