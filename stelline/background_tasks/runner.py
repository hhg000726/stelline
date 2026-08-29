"""운영에서만 실행할 장기 실행 작업의 단일 시작 지점."""

from stelline.apis.bugs.bugs import start_rank_refresh
from stelline.apis.search.search import start_search_scheduler
from stelline.background_tasks.monitoring import start_monitoring


def start_background_tasks():
    start_monitoring()
    start_search_scheduler()
    start_rank_refresh()
