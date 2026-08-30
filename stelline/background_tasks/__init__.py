"""운영에서만 실행할 장기 실행 작업의 단일 시작 지점."""

import logging

from stelline.apis.bugs.tasks import start_rank_refresh
from stelline.apis.search.tasks import start_search_scheduler
from stelline.background_tasks.monitoring import start_monitoring


def start_background_tasks():
    logging.info("백그라운드 작업 시작 요청을 받았습니다.")
    start_monitoring()
    start_search_scheduler()
    start_rank_refresh()
    logging.info("백그라운드 작업 스레드 등록 완료")
