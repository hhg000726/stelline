"""관리자 화면 '검색 점검 곡' 표에 붙이는 노출 상태.

값은 공개 화면과 같은 판정(stelline/apis/search/history.py)에서 나온다. 관리자 표에만 따로 계산하면
두 화면이 서로 다른 말을 하게 되므로, 여기서는 글자로 바꾸고 순서만 정한다. 시각은 한국 시간이다.
"""

from datetime import timedelta

from stelline.apis.search.history import (
    BLOCKED,
    CHECK_RETENTION,
    COVER_ONLY,
    RECENT_WINDOW,
    RETRY_WINDOW,
    UNCHECKED,
    VISIBLE,
    build_statuses,
    is_retry_target,
    summarize_statuses,
    utc_now,
)
from stelline.apis.search.tasks import read_search_checks

KST_OFFSET = timedelta(hours=9)

# 현재 상태(마지막 검사 결과)의 이름. 공개 화면의 탭 이름과 맞춘다.
STATE_LABELS = {
    BLOCKED: "막힘",
    COVER_ONLY: "cover로만 찾힘",
    VISIBLE: "정상",
    UNCHECKED: "검사 기록 없음",
}
NO_VIDEO_LABEL = "영상 ID 없음(검사 안 함)"


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


def annotate_song_rows(rows, connection, now=None):
    """표의 각 행에 현재 상태·마지막 검사·최근 7일·위험도 칸을 붙이고, 표 위에 둘 요약을 만든다.

    곡 목록은 표가 이미 읽은 행을 그대로 쓰고, 검사 기록만 같은 연결로 더 읽는다.
    덧붙인 칸은 표시용이다. 수정·삭제는 검색어(key_fields)로만 행을 찾으므로 영향이 없다.
    """
    now = now or utc_now()
    with connection.cursor() as cursor:
        checks = read_search_checks(cursor, now - CHECK_RETENTION)
    statuses = build_statuses(rows, checks, now)

    annotated = []
    for row in rows:
        status = statuses.get(row.get("query"))
        if status is None or status.video_id != row.get("video_id"):
            # 영상 ID 가 비어 있으면 무엇을 찾아야 할지 몰라 검사하지 않는다.
            extra = {"search_state": NO_VIDEO_LABEL, "search_checked": "", "search_week": "", "search_risk": ""}
            order = 5
        else:
            extra = {
                "search_state": STATE_LABELS[status.state],
                "search_checked": (
                    f"{status.checked_at + KST_OFFSET:%m/%d %H:%M} ({_ago(now - status.checked_at)})"
                    if status.checked_at else ""
                ),
                "search_week": _week_text(status.week),
                "search_risk": f"{status.risk}%" if status.risk is not None else "",
            }
            order = _order(status)
        annotated.append((order, row.get("query") or "", {**row, **extra}))
    annotated.sort(key=lambda item: (item[0], item[1]))

    summary = summarize_statuses(statuses.values())
    retry = [s for s in statuses.values() if is_retry_target(s)]
    sweep_waited = [now - s.checked_at for s in statuses.values() if s.checked_at and not is_retry_target(s)]
    overview = {
        # 공개 화면의 탭과 같은 숫자다(지금 막힘·최근 7일·cover 검색으로 발견).
        "tabs": [
            ("지금 막힘", summary[BLOCKED]),
            (f"최근 {RECENT_WINDOW.days}일 안에 검색이 안 된 곡", summary["recent"]),
            ("cover로만 찾힘", summary[COVER_ONLY]),
            ("검사 기록 없음", summary[UNCHECKED]),
        ],
        "songs": summary["songs"],
        "checked_in_window": summary["checked_in_window"],
        "window_days": RECENT_WINDOW.days,
        "retry_days": RETRY_WINDOW.days,
        "retry_count": len(retry),
        # 재시도 대상 가운데 가장 오래 다시 시도하지 못한 곡. 재시도가 얼마나 자주 돌아오는지 보인다.
        "retry_wait_hours": (
            round(max(now - s.checked_at for s in retry).total_seconds() / 3600) if retry else None
        ),
        # 순회 곡 가운데 가장 오래 검사하지 않은 곡이 며칠 전에 검사됐는지. 한 바퀴 도는 기간과 같다.
        "sweep_wait_days": round(max(sweep_waited).total_seconds() / 86400, 1) if sweep_waited else None,
    }
    return [row for _, _, row in annotated], overview
