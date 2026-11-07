import logging

from flask import jsonify

from stelline.apis.reports import handle_report_submission
from stelline.config import SEARCH_API_INTERVAL
from stelline.database.connection import database_cursor
from .history import BLOCKED, COVER_ONLY, RECENT_WINDOW, summarize_statuses, to_epoch
from .tasks import load_song_statuses, next_search_run_epoch, search_run_hours_kst


def _sorted_statuses():
    statuses, now = load_song_statuses()
    return sorted(statuses.values(), key=lambda status: status.query), now


def _last_checked_at(statuses):
    moments = [status.checked_at for status in statuses if status.checked_at]
    return to_epoch(max(moments)) if moments else None


def _song_json(status):
    return {
        "query": status.query,
        "video_id": status.video_id,
        # 현재 상태(마지막 검사 결과). '지금 막힘'·'cover 검색으로 발견' 탭이 이것으로 거른다.
        "state": status.state,
        # 최근 7일 안에 검색이 안 된(막힘·cover로만) 적이 있는지. '최근 7일' 탭이 이것으로 거른다.
        "recent": status.recent_problem,
        # 최근 14일 안에 검색이 안 된 적이 있어 회차마다 우선 다시 시도하는 곡인지.
        "retry": status.retry,
        "checked_at": to_epoch(status.checked_at),
        "fallback_query": status.fallback_query,
        "last_problem_at": to_epoch(status.last_problem_at),
        "week": {
            "checks": status.week["checks"],
            "visible": status.week["visible"],
            "cover_only": status.week["cover_only"],
            "blocked": status.week["blocked"],
            "results": [{"at": to_epoch(moment), "result": result} for moment, result in status.week_results],
        },
        "risk": status.risk,
    }


# 요청 기록은 DEBUG 다. 화면을 열 때마다 생기고, 들어왔다는 사실은 nginx 접속 로그에 있다.
def get_search_status():
    """검색 화면이 쓰는 곡별 노출 상태. 판정은 history.py 한 곳에서만 한다."""
    logging.debug("검색 노출 상태 조회 요청")
    statuses, now = _sorted_statuses()
    return jsonify({
        "generated_at": to_epoch(now),
        "last_checked_at": _last_checked_at(statuses),
        "window_days": RECENT_WINDOW.days,
        # 검색 일정. 화면은 이 값으로 '다음 검색' 시각을 보여 주고, 간격을 글자로 적어 두지 않는다.
        "schedule": {
            "interval_hours": SEARCH_API_INTERVAL // 3600,
            "run_hours_kst": search_run_hours_kst(),
            "next_run_at": next_search_run_epoch(to_epoch(now)),
        },
        "summary": summarize_statuses(statuses),
        "songs": [_song_json(status) for status in statuses],
    })


def get_not_searched():
    """예전 화면 모양 그대로의 응답. 바깥에서 이 주소를 읽는 쪽(StellaAPI 등)을 위해 키를 유지한다.

    값은 새 판정에서 만든다.
    - all_songs: 지금 막힌 곡(곡마다 마지막 검사 결과 기준. 예전에는 마지막 한 회차에서 실패한 곡뿐이었다)
    - recent: 최근 7일 안에 막힌 적이 있는 곡. searched_time 은 마지막으로 막힌 시각
    - cover_matches: 지금 cover 를 붙여야만 찾히는 곡
    - searched_time: 마지막 검사 시각(기록이 없으면 0)
    """
    logging.debug("미검색곡 조회 요청")
    statuses, _ = _sorted_statuses()
    recent = []
    for status in statuses:
        blocked_at = [moment for moment, result in status.week_results if result == BLOCKED]
        if blocked_at:
            recent.append({"query": status.query, "video_id": status.video_id, "searched_time": to_epoch(blocked_at[-1])})
    return jsonify({
        "all_songs": [{"query": s.query, "video_id": s.video_id} for s in statuses if s.state == BLOCKED],
        "searched_time": _last_checked_at(statuses) or 0,
        "recent": recent,
        "cover_matches": [
            {"query": s.query, "video_id": s.video_id, "fallback_query": s.fallback_query}
            for s in statuses if s.state == COVER_ONLY
        ],
    })


def get_song_infos():
    """검색어 목록. 예전 키(video_id·query·risk·fallback_query)를 유지하고 상태를 덧붙인다.

    risk 는 이제 '최근 30일 중 기본 검색에서 안 보인 시간의 비율(0~100)'이고, 기록이 없으면 null 이다.
    """
    logging.debug("곡 메타 정보 조회 요청")
    statuses, _ = _sorted_statuses()
    return jsonify([
        {
            "video_id": status.video_id,
            "query": status.query,
            "risk": status.risk,
            "fallback_query": status.fallback_query,
            "state": status.state,
            "checked_at": to_epoch(status.checked_at),
        }
        for status in statuses
    ])


def record_search():
    logging.debug("검색 기록 카운트 증가 요청")
    try:
        with database_cursor() as cursor:
            cursor.execute("UPDATE record_search SET copy_count = copy_count + 1")
    except Exception:
        logging.exception("RDS record_search의 copy_count 업데이트 실패")

    return '', 204


def submit_song_report():
    return handle_report_submission("song_reports", "노래 제보")
