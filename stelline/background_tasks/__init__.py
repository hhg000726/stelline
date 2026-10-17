"""운영에서만 실행할 장기 실행 작업의 단일 시작 지점."""

import logging

try:
    import fcntl
except ImportError:  # 윈도우 개발 환경. 여러 프로세스로 띄울 일이 없다.
    fcntl = None

from stelline.apis.bugs.tasks import start_rank_refresh
from stelline.apis.search.tasks import start_search_scheduler
from stelline.background_tasks.monitoring import start_monitoring
from stelline.config import PROJECT_ROOT, START_BACKGROUND_TASKS

# gunicorn 워커를 여럿 띄우면 워커마다 앱을 불러 작업도 워커 수만큼 돈다.
# 그러면 YouTube 할당량을 그만큼 더 쓰고, 조회수 달성 알림도 같은 사람에게 여러 번 나간다.
# 서버 한 대에서 한 프로세스만 작업을 맡도록 파일 잠금을 잡는다.
LOCK_PATH = PROJECT_ROOT / ".background_tasks.lock"

# 잠금은 파일이 열려 있는 동안만 유지되므로 프로세스가 끝날 때까지 붙들고 있는다.
_lock_handle = None


def acquire_runner_lock(path=LOCK_PATH):
    """이 프로세스가 작업을 맡아도 되면 True. 다른 프로세스가 이미 맡았으면 False."""
    global _lock_handle
    if fcntl is None:
        return True
    try:
        handle = open(path, "a", encoding="utf-8")
    except OSError:
        # 잠금 파일을 못 만든다고 작업을 통째로 멈추면 그쪽이 더 큰 손해다.
        logging.warning("백그라운드 작업 잠금 파일을 열 수 없어 잠금 없이 시작합니다: %s", path)
        return True
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    _lock_handle = handle
    return True


def start_background_tasks():
    logging.info("백그라운드 작업 시작 요청을 받았습니다.")
    if not acquire_runner_lock():
        logging.info("다른 프로세스가 백그라운드 작업을 맡고 있어 이 프로세스에서는 시작하지 않습니다.")
        return
    start_monitoring()
    start_search_scheduler()
    start_rank_refresh()
    logging.info("백그라운드 작업 스레드 등록 완료")


def start_background_tasks_if_enabled():
    """서버 프로세스가 뜰 때 부르는 진입점. START_BACKGROUND_TASKS 가 꺼져 있으면 아무것도 하지 않는다.

    개발에서는 기본적으로 꺼 두어 외부 API와 운영 알림을 건드리지 않는다.
    """
    if START_BACKGROUND_TASKS:
        start_background_tasks()
    else:
        logging.info("START_BACKGROUND_TASKS=false 라 백그라운드 작업을 시작하지 않습니다.")
