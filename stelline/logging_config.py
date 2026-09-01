import logging
import os
from logging.handlers import TimedRotatingFileHandler

# 공통 설정 변수
LOG_DIR = "./logs"  # 로그 파일 저장 경로 (필요에 따라 변경 가능)
os.makedirs(LOG_DIR, exist_ok=True)
LOG_ROTATION_TIME = "midnight"  # 로그 롤링 시간
LOG_INTERVAL = 1  # 롤링 간격 (ex: 1일마다)
LOG_BACKUP_DAYS = 7  # 보관할 로그 백업 개수

# 로그 포맷 설정
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")


# 로그 핸들러 설정 함수
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
    # 최상위 로거 가져오기
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.propagate = False

    # 개별 로그 핸들러 설정
    info_handler = create_log_handler("app_info.log", logging.INFO)
    warning_handler = create_log_handler("app_warning.log", logging.WARNING)
    error_handler = create_log_handler("app_error.log", logging.ERROR)

    # 핸들러 추가
    logger.addHandler(info_handler)
    logger.addHandler(warning_handler)
    logger.addHandler(error_handler)

    # 로깅 레벨 설정
    logger.setLevel(logging.INFO)
    logger.info("로그 설정이 초기화되었습니다. 로그 디렉터리: %s", LOG_DIR)