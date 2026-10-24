"""앱 전체의 로그 설정.

`logs/` 아래에 수준별로 쌓고, 자정마다 새 파일로 넘기며, 7일이 지난 것은 지운다.

- `app_info.log`: INFO 이상 전부
- `app_warning.log`: WARNING 이상
- `app_error.log`: ERROR 이상
- `app_event.log`: `events` 로거로 남긴 운영 기록만. 관리자 화면의 '운영 로그' 탭이 읽는다.

한 줄은 `시각 [수준] {스레드} 내용` 모양이다. 시각은 서버 시간대와 상관없이 한국 시간이다.
API 키처럼 남으면 안 되는 값은 파일에 쓰기 직전에 가린다(`redact`).
"""

import logging
import os
import re
import time
from datetime import date, timedelta
from logging.handlers import TimedRotatingFileHandler

# 테스트는 임시 폴더를 넘겨, 개발 폴더의 logs/ 에 테스트 로그가 섞이지 않게 한다.
LOG_DIR = os.getenv("LOG_DIR", "./logs")
LOG_ROTATION_TIME = "midnight"
LOG_INTERVAL = 1
# 이 날수보다 오래된 로그는 지운다.
LOG_KEEP_DAYS = 7

INFO_LOG_FILE = "app_info.log"
WARNING_LOG_FILE = "app_warning.log"
ERROR_LOG_FILE = "app_error.log"
EVENT_LOG_FILE = "app_event.log"
# 수준별로 파일을 나눈다. 각 파일에는 그 수준 이상만 쌓인다.
LOG_FILES = (
    (INFO_LOG_FILE, logging.INFO),
    (WARNING_LOG_FILE, logging.WARNING),
    (ERROR_LOG_FILE, logging.ERROR),
)
LOG_NAMES = frozenset({name for name, _ in LOG_FILES} | {EVENT_LOG_FILE})

# 운영자가 알아야 할 일(검색 점검 결과, 관리자 작업, 달성 알림, 서버 시작)은 이 로거로 남긴다.
# 다른 로그처럼 수준별 파일에도 쌓이고, app_event.log 에는 이 로거의 것만 쌓인다.
# 요청마다 생기는 일은 여기에 남기지 않는다. 그러면 정작 봐야 할 기록이 묻힌다.
EVENT_LOGGER_NAME = "stelline.events"
events = logging.getLogger(EVENT_LOGGER_NAME)

LINE_FORMAT = "%(asctime)s [%(levelname)s] {%(threadName)s} %(message)s"

KST_OFFSET_SECONDS = 9 * 3600

# 가릴 값들. 요청 주소의 key=… (YouTube Data API 는 키를 주소에 싣는다), 구글 API 키 모양,
# 인증 헤더의 토큰.
_SECRET_PATTERNS = (
    (re.compile(r"([?&](?:key|api_key|access_token)=)[^&\s'\"<>]+", re.IGNORECASE), r"\1<가림>"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "<가림>"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/\-]+=*", re.IGNORECASE), r"\1<가림>"),
)

_BACKUP_NAME_RE = re.compile(r"^(?P<name>app_[a-z]+\.log)\.(?P<day>\d{4}-\d{2}-\d{2})$")


def redact(text):
    """로그에 남으면 안 되는 값을 가린다. 관리자 화면도 예전 줄을 보여 주기 전에 이것을 거친다."""
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _korea_time(seconds):
    # 한국은 서머타임이 없어 9시간을 더하기만 하면 된다. 관리자 화면도 한국 시간으로 읽는다.
    return time.gmtime(seconds + KST_OFFSET_SECONDS)


class RedactingFormatter(logging.Formatter):
    """예외 내용까지 붙인 줄 전체에서 비밀 값을 가린 뒤 내보낸다.

    requests 의 HTTPError 문구에는 요청 주소가 통째로 들어간다. 주소에 키를 싣는 YouTube API 는
    실패할 때마다 키가 로그에 그대로 남았다. 호출하는 쪽에서 문구를 고쳐도, 빠뜨린 곳이 하나라도
    있으면 다시 샌다. 그래서 파일에 쓰기 직전에 한 번 더 막는다.
    """

    converter = staticmethod(_korea_time)

    def format(self, record):
        return redact(super().format(record))


def is_event_record(record):
    return record.name == EVENT_LOGGER_NAME


def purge_old_logs(log_dir=None, today=None, now=None):
    """LOG_KEEP_DAYS 보다 오래된 로그를 지운다.

    - 넘긴 파일(`app_info.log.2026-10-17` 등)은 이름에 붙은 날짜로 판단한다.
    - 아직 넘기지 않은 파일도 마지막으로 쓴 지 그만큼 지났으면, 안의 줄이 모두 그보다 오래된
      것이라 비운다. 경고·오류 파일은 새 줄이 와야 다음 파일로 넘어가므로, 조용한 기간이 길면
      몇 주 전 줄이 그대로 남는다. 지우지 않고 비우는 까닭은, 처리기가 열어 둔 파일을 지우면
      그 뒤에 쓰는 줄이 사라진 파일로 들어가 버리기 때문이다.
    """
    log_dir = log_dir or LOG_DIR
    today = today or date.today()
    now = time.time() if now is None else now
    cutoff = today - timedelta(days=LOG_KEEP_DAYS)
    try:
        names = os.listdir(log_dir)
    except OSError:
        return
    for name in names:
        path = os.path.join(log_dir, name)
        try:
            backup = _BACKUP_NAME_RE.match(name)
            if backup and backup["name"] in LOG_NAMES:
                if date.fromisoformat(backup["day"]) < cutoff:
                    os.remove(path)
            elif name in LOG_NAMES and os.path.getsize(path) and os.path.getmtime(path) < now - LOG_KEEP_DAYS * 86400:
                os.truncate(path, 0)
        except (OSError, ValueError):
            # 다른 프로세스가 먼저 지웠거나(배포 때 마이그레이션도 앱을 불러온다) 윈도우에서
            # 열려 있어 못 지운 것이다. 다음 정리 때 다시 본다.
            continue


class DailyLogHandler(TimedRotatingFileHandler):
    """자정마다 새 파일로 넘기고, 넘길 때마다 오래된 로그를 정리한다.

    기본 처리기는 날짜와 상관없이 '최근 n개'를 남긴다. 경고·오류 파일은 무언가 남은 날에만
    생기므로, 7개를 남기면 몇 주 전 오류 로그까지 남았다. 그래서 개수가 아니라 날짜로 지운다.
    INFO 파일은 5분마다 쓰여 날마다 넘어가므로, 정리도 하루 한 번은 꼭 돈다.
    """

    def doRollover(self):
        super().doRollover()
        purge_old_logs(os.path.dirname(self.baseFilename))


def create_log_handler(log_dir, filename, level):
    # 인코딩을 정하지 않으면 OS 기본값(윈도우는 cp949)을 쓴다. 로그에 한글 밖의
    # 문자가 섞이면 그 줄이 통째로 사라지므로 utf-8로 못 박는다.
    # delay=True: 실제로 기록할 때까지 파일을 열지 않는다.
    # backupCount=0: 개수로 지우지 않는다. 지우는 일은 purge_old_logs 가 날짜로 한다.
    handler = DailyLogHandler(
        os.path.join(log_dir, filename),
        when=LOG_ROTATION_TIME,
        interval=LOG_INTERVAL,
        backupCount=0,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(RedactingFormatter(LINE_FORMAT))
    handler.setLevel(level)
    return handler


def build_handlers(log_dir):
    handlers = [create_log_handler(log_dir, filename, level) for filename, level in LOG_FILES]
    event_handler = create_log_handler(log_dir, EVENT_LOG_FILE, logging.INFO)
    event_handler.addFilter(is_event_record)
    handlers.append(event_handler)
    return handlers


def setup_logging(log_dir=None):
    log_dir = log_dir or LOG_DIR
    os.makedirs(log_dir, exist_ok=True)
    purge_old_logs(log_dir)
    logger = logging.getLogger()
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        # 남이 단 처리기(pytest 의 로그 수집 등)는 닫지 않는다. 그쪽이 계속 쓴다.
        if isinstance(handler, DailyLogHandler):
            handler.close()
    logger.propagate = False
    for handler in build_handlers(log_dir):
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.info("로그 설정이 초기화되었습니다. 로그 디렉터리: %s", log_dir)
