"""관리자 화면 '검색 점검' 탭에 붙이는 노출 상태와 다음 검색.

값은 공개 화면과 같은 판정(stelline/apis/search/history.py)과 같은 순서 계산(tasks.plan_next_run)에서
나온다. 관리자 화면에만 따로 계산하면 두 화면이 서로 다른 말을 하게 되므로, 여기서는 글자로 바꾸고
순서만 정한다. 시각은 한국 시간이다.
"""

from datetime import timedelta

from stelline.apis.search.history import (
    BLOCKED,
    CHECK_RETENTION,
    COVER_ONLY,
    REASON_FIRST,
    REASON_RETRY,
    REASON_SWEEP,
    RECENT_WINDOW,
    RETRY_WINDOW,
    UNCHECKED,
    VISIBLE,
    build_statuses,
    is_retry_target,
    last_run,
    summarize_statuses,
    utc_now,
)
from stelline.apis.search.tasks import plan_next_run, read_search_checks, read_search_requests

KST_OFFSET = timedelta(hours=9)

# 현재 상태(마지막 검사 결과)의 이름. 공개 화면의 탭 이름과 맞춘다.
STATE_LABELS = {
    BLOCKED: "막힘",
    COVER_ONLY: "cover로만 찾힘",
    VISIBLE: "정상",
    UNCHECKED: "검사 기록 없음",
}
NO_VIDEO_LABEL = "영상 ID 없음(검사 안 함)"
REASON_LABELS = {REASON_FIRST: "관리자 요청", REASON_RETRY: "재시도", REASON_SWEEP: "순회"}


def _order(status):
    """표에서 손볼 곡이 위로 오게 한다: 막힘 → cover로만 → 7일 안에 문제가 있었던 정상 곡 → 기록 없음 → 정상."""
    if status.state == BLOCKED:
        return 0
    if status.state == COVER_ONLY:
        return 1
    if status.recent_problem:
        return 2
    if status.state == UNCHECKED:
        return 3
    return 4


def _kst(moment):
    return f"{moment + KST_OFFSET:%m/%d %H:%M}"


def _ago(delta):
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return "1시간 안"
    if hours < 24:
        return f"{int(hours)}시간 전"
    return f"{int(hours // 24)}일 전"


def _week_text(week):
    if not week["checks"]:
        return ""
    parts = [f"{week['checks']}번"]
    if week[BLOCKED]:
        parts.append(f"막힘 {week[BLOCKED]}")
    if week[COVER_ONLY]:
        parts.append(f"cover {week[COVER_ONLY]}")
    return " · ".join(parts)


def _stats(statuses, now):
    """표 위에 둘 짧은 숫자 줄: (이름, 값, 마우스를 올리면 보일 설명)."""
    summary = summarize_statuses(statuses)
    retry = [s for s in statuses if is_retry_target(s)]
    sweep_waited = [now - s.checked_at for s in statuses if s.checked_at and not is_retry_target(s)]
    retry_wait = max((now - s.checked_at for s in retry), default=None)
    return [
        ("지금 막힘", f"{summary[BLOCKED]}곡", "마지막 검사에서 기본·cover·웹 검색 모두 못 찾은 곡"),
        (f"최근 {RECENT_WINDOW.days}일", f"{summary['recent']}곡", f"{RECENT_WINDOW.days}일 안에 막힘이나 cover로만이 한 번이라도 나온 곡"),
        ("cover로만", f"{summary[COVER_ONLY]}곡", "마지막 검사에서 cover 를 붙여야만 찾은 곡"),
        ("검사 전", f"{summary[UNCHECKED]}곡", "검사 기록이 없는 곡. 순회에서 먼저 검사한다"),
        ("재시도 대상", f"{len(retry)}곡" + (f" · 최장 {round(retry_wait.total_seconds() / 3600)}시간" if retry_wait else ""),
         f"{RETRY_WINDOW.days}일 안에 검색이 안 된 적이 있어 회차마다 먼저 다시 시도하는 곡. 최장은 그중 가장 오래 기다린 곡"),
        (f"{RECENT_WINDOW.days}일 검사", f"{summary['checked_in_window']}/{summary['songs']}곡", f"최근 {RECENT_WINDOW.days}일 동안 한 번이라도 검사한 곡"),
        ("한 바퀴", f"{max(sweep_waited).total_seconds() / 86400:.1f}일" if sweep_waited else "—",
         "재시도 대상이 아닌 곡 가운데 가장 오래 검사하지 않은 곡이 며칠 전에 검사됐는지"),
    ]


def search_tab_views(rows, connection, now=None):
    """'검색 점검' 탭에 필요한 것을 한 번에 만든다: 상태 열을 붙인 곡 행, 숫자 줄, 지난·다음 회차.

    곡 목록은 표가 이미 읽은 행을 그대로 쓰고, 검사 기록과 요청만 같은 연결로 더 읽는다.
    덧붙인 칸은 표시용이다. 수정·삭제는 검색어(key_fields)로만 행을 찾으므로 영향이 없다.
    """
    now = now or utc_now()
    with connection.cursor() as cursor:
        checks = read_search_checks(cursor, now - CHECK_RETENTION)
        requests = read_search_requests(cursor)
    statuses = build_statuses(rows, checks, now)
    state = {"songs": rows, "checks": checks, "requests": requests, "now": now, "statuses": statuses}

    annotated = []
    for row in rows:
        status = statuses.get(row.get("query"))
        if status is None or status.video_id != row.get("video_id"):
            # 영상 ID 가 비어 있으면 무엇을 찾아야 할지 몰라 검사하지 않는다.
            extra = {"search_state": NO_VIDEO_LABEL, "search_checked": "", "search_week": ""}
            order = 5
        else:
            extra = {
                "search_state": STATE_LABELS[status.state],
                "search_checked": (
                    f"{_kst(status.checked_at)} ({_ago(now - status.checked_at)})" if status.checked_at else ""
                ),
                "search_week": _week_text(status.week),
            }
            order = _order(status)
        annotated.append((order, row.get("query") or "", {**row, **extra}))
    annotated.sort(key=lambda item: (item[0], item[1]))

    plan = plan_next_run(state)
    previous = last_run(checks, statuses)
    next_run = {
        "when": _kst(plan["starts_at"]),
        "sure": plan["sure"],
        "most": len(plan["order"]),
        "items": [
            {
                "query": status.query,
                "reason": reason,
                "reason_label": REASON_LABELS[reason],
                "state_label": STATE_LABELS[status.state],
                "sure": index < plan["sure"],
            }
            for index, (status, reason) in enumerate(plan["order"])
        ],
        "skipped": plan["skipped"],
        "queries": sorted(statuses),
    }
    last = None
    if previous:
        counts = {result: sum(1 for _, r in previous["songs"] if r == result) for result in (BLOCKED, COVER_ONLY, VISIBLE)}
        last = {
            "when": _kst(previous["started_at"]),
            "songs": [(query, STATE_LABELS[result]) for query, result in previous["songs"]],
            "counts": f"막힘 {counts[BLOCKED]} · cover로만 {counts[COVER_ONLY]} · 정상 {counts[VISIBLE]}",
        }
    return {
        "rows": [row for _, _, row in annotated],
        "stats": _stats(list(statuses.values()), now),
        "next_run": next_run,
        "last_run": last,
    }
