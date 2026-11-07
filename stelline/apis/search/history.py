"""검색 노출 판정 기준. 모든 판정은 곡별 검사 기록(`search_checks`)에서 나온다.

세 가지를 서로 다른 기준으로 따로 판단한다. 기준끼리 값을 빌려 쓰지 않으므로 하나를 바꿔도
나머지는 그대로다.

- 현재 상태: 그 곡(검색어 + 영상 ID)의 **가장 최근 검사 결과**. 어느 회차에서 검사했는지는 묻지 않는다.
  예전에는 '마지막 한 회차에서 실패한 곡'만 막힘으로 보여서, 그 회차에 검사하지 않은 곡은
  다시 확인하지도 않았는데 목록에서 빠졌다.
- 최근 7일 현황: 지금 시각부터 거꾸로 7일(RECENT_WINDOW) 안의 검사 결과 전부. 이 안에 검색이 안 된
  결과(막힘·cover로만)가 한 번이라도 있으면 recent_problem 이다.
- 검색 대상: 최근 14일(RETRY_WINDOW) 안에 검색이 안 된 적이 있는 곡을 회차마다 우선 다시 시도하고,
  나머지 곡은 회차 예산의 일부(SWEEP_SHARE)로 차례로 돌아가며 확인한다(select_search_targets).

화면의 탭은 이 판정을 그대로 거른다. '지금 막힘'은 현재 상태가 막힘, 'cover 검색으로 발견'은 현재
상태가 cover로만, '최근 7일'은 recent_problem 인 곡이다. 한 곡이 '지금 막힘'과 '최근 7일'에 함께
나올 수 있는데, 두 탭은 서로 다른 질문(지금은 어떤가 / 지난 7일은 어땠나)에 답하기 때문이다.

재시도 기간(14일)을 화면의 7일보다 길게 둔 것은 일부러다. 운영 기록을 보면 한 번 막힌 곡은
풀렸다가 다시 막히는 일이 잦다. 7일로 자르면 그런 곡을 순회 차례까지 기다려야 해서 다시 막힌 것을
늦게 찾는다(로그로 추정한 모의 실험에서 발견까지 중앙값 1.3일 → 14일로 두면 0.3일).

위험도는 이 셋 어디에도 쓰지 않는다. 예전 위험도(실패하면 28, 성공마다 1씩 감소)는 검사 횟수로
세는 값이라, 하루 회차 수나 한 회차에 검사하는 곡 수가 바뀌면 '7일'이라는 뜻이 무너졌다
(하루 3회·우선 15곡이 되자 실제로는 19일쯤을 뜻했다). 지금 위험도는 '최근 30일 중 기본 검색에서
안 보인 시간의 비율'로, 관리자가 자주 막히는 곡을 찾는 참고 지표일 뿐이다.

이 모듈은 DB 를 모른다. 기록과 시각(now)을 받아서만 판단하므로 같은 기록이면 언제 계산해도
답이 같고, 시험도 시각을 정해 놓고 할 수 있다. 시각은 모두 UTC(시간대 없는 datetime)다.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# ---------- 검사 결과 ----------
# 기본 검색(YouTube API, 안 되면 웹 검색 결과 페이지)에서 영상이 상위 3개 안에 보였다.
VISIBLE = "visible"
# 기본 검색에서는 못 찾았고, 검색어 뒤에 cover 를 붙인 검색에서만 찾았다.
COVER_ONLY = "cover_only"
# 기본 검색·cover 검색·웹 검색 결과 페이지 모두에서 못 찾았다.
BLOCKED = "blocked"
RESULTS = (VISIBLE, COVER_ONLY, BLOCKED)
# 기본 검색어로 안 보인 결과. '검색이 안 됐다'는 말은 이 둘을 가리킨다.
PROBLEM_RESULTS = (COVER_ONLY, BLOCKED)
# 현재 상태로만 쓰는 값. 이 곡(검색어 + 영상 ID)의 검사 기록이 하나도 없다.
UNCHECKED = "unchecked"

# ---------- 기간(모두 지금 시각에서 거꾸로 센다. 달력 날짜나 회차 수와 무관하다) ----------
# 화면의 '최근 7일' 탭과 카드의 7일 기록.
RECENT_WINDOW = timedelta(days=7)
# 검색 대상: 이 안에 검색이 안 된 적이 있으면 회차마다 우선 다시 시도한다.
RETRY_WINDOW = timedelta(days=14)
# 위험도를 계산하는 기간.
RISK_WINDOW = timedelta(days=30)
# 검사 기록을 남겨 두는 기간. 위 기간들보다 길어야 기간이 시작할 때의 상태를 안다.
CHECK_RETENTION = timedelta(days=90)

# ---------- 검색 대상 ----------
# 나머지 곡(재시도 대상이 아닌 곡)을 확인하는 데 떼어 두는 회차 예산의 몫(곡 수는 소수점 버림).
# 재시도 대상이 예산보다 많아도 오래 문제없던 곡이 새로 막힌 것을 놓치지 않게 회차마다 이만큼은
# 반드시 순회한다. 30회 × 15% = 4곡. 로그로 추정한 모의 실험(하루 3회 × 30회 기준)에서 20%(6곡)는
# 화면 정확도가 조금 더 높았지만 막힌 곡 재시도 간격이 예전(14시간)보다 길어져(16시간),
# 재시도를 앞세워 15%(12시간)로 정했다.
SWEEP_SHARE = 0.15

# 관리자가 다음 회차를 조정한 요청(search_requests.action). 다음 회차에 한 번만 적용한다.
REQUEST_FIRST = "first"  # 다음 회차 맨 앞에서 검사한다(요청한 순서대로)
REQUEST_SKIP = "skip"    # 다음 회차 순서에서 뺀다
REQUEST_ACTIONS = (REQUEST_FIRST, REQUEST_SKIP)

# 다음 회차 순서에서 곡마다 붙는 이유. 화면과 관리자 표가 이 이름으로 표시한다.
REASON_FIRST = "first"   # 관리자 요청
REASON_RETRY = "retry"   # 최근 14일 안에 검색이 안 된 적이 있어 다시 시도
REASON_SWEEP = "sweep"   # 나머지 곡 순회

COVER_SUFFIX = " cover"


def utc_now():
    """검사 기록과 판정에 쓰는 '지금'. DB 서버 시간대와 상관없이 앱이 UTC 로 정한다."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_epoch(moment):
    """UTC datetime → 초 단위 epoch. 화면(JS)은 이 값을 받아 보는 사람의 시간대로 바꾼다."""
    return moment.replace(tzinfo=timezone.utc).timestamp() if moment else None


def cover_query(query):
    return f"{query}{COVER_SUFFIX}"


def _empty_week():
    return {"checks": 0, VISIBLE: 0, COVER_ONLY: 0, BLOCKED: 0}


@dataclass
class SongStatus:
    query: str
    video_id: str
    # 현재 상태: VISIBLE / COVER_ONLY / BLOCKED / UNCHECKED
    state: str = UNCHECKED
    # 마지막 검사 시각(UTC). 기록이 없으면 None.
    checked_at: datetime | None = None
    # 현재 상태가 COVER_ONLY 일 때 찾은 검색어.
    fallback_query: str | None = None
    # 최근 7일 결과 수와, 오래된 것부터 늘어놓은 (시각, 결과).
    week: dict = field(default_factory=_empty_week)
    week_results: list = field(default_factory=list)
    # 남아 있는 기록 가운데 마지막으로 검색이 안 된(COVER_ONLY·BLOCKED) 시각.
    last_problem_at: datetime | None = None
    # 최근 7일 안에 검색이 안 된 적이 있다('최근 7일' 탭). build_statuses 가 그때의 now 로 정한다.
    recent_problem: bool = False
    # 최근 14일 안에 검색이 안 된 적이 있어 회차마다 우선 다시 시도한다(검색 대상).
    retry: bool = False
    # 최근 30일 중 문제 상태였던 시간 비율(0~100). 기록이 없으면 None.
    risk: int | None = None


def _risk_percent(rows, now):
    """최근 30일 중 기본 검색에서 안 보였던 시간의 비율.

    결과 하나는 다음 검사 전까지 유지된다고 본다. 검사 횟수로 세면 문제 곡을 더 자주 검사하는
    만큼 문제가 부풀려지고, 검사 간격이 바뀌면 같은 곡도 값이 달라진다.
    """
    if not rows:
        return None
    start = now - RISK_WINDOW
    before = [row for row in rows if row["checked_at"] < start]
    inside = [row for row in rows if row["checked_at"] >= start]
    # 기간이 시작할 때의 상태는 그 앞의 마지막 기록으로 안다. 없으면 첫 기록부터 센다.
    segments = ([(start, before[-1]["result"])] if before else []) + [
        (row["checked_at"], row["result"]) for row in inside
    ]
    observed = now - segments[0][0]
    if observed <= timedelta(0):
        return 100 if segments[-1][1] in PROBLEM_RESULTS else 0
    problem = timedelta(0)
    for (moment, result), (until, _) in zip(segments, segments[1:] + [(now, None)]):
        if result in PROBLEM_RESULTS and until > moment:
            problem += min(until, now) - moment
    return round(100 * (problem / observed))


def build_statuses(songs, checks, now):
    """곡 목록과 검사 기록으로 곡마다 현재 상태·최근 7일·재시도 여부·위험도를 계산한다.

    기록은 검색어와 영상 ID 가 둘 다 같은 것만 그 곡의 것으로 본다. 관리자가 영상 ID 나
    검색어를 바꾸면 예전 결과는 다른 대상을 검사한 것이므로 쓰지 않고, 그 곡은 기록이 없는
    곡이 되어 다음 회차에 먼저 검사한다. 모르는 결과 값은 건너뛴다.
    """
    grouped = {}
    for row in checks:
        if row.get("result") not in RESULTS or row.get("checked_at") is None:
            continue
        grouped.setdefault((row["query"], row["video_id"]), []).append(row)

    week_start = now - RECENT_WINDOW
    statuses = {}
    for song in songs:
        query, video_id = song.get("query"), song.get("video_id")
        if not query or not video_id:
            continue  # 영상 ID 가 없으면 무엇을 찾아야 할지 모른다. 검사 대상도 아니다.
        rows = sorted(grouped.get((query, video_id), ()), key=lambda r: (r["checked_at"], r.get("id") or 0))
        status = SongStatus(query=query, video_id=video_id)
        if rows:
            latest = rows[-1]
            status.state = latest["result"]
            status.checked_at = latest["checked_at"]
            if status.state == COVER_ONLY:
                status.fallback_query = latest.get("fallback_query") or cover_query(query)
            for row in rows:
                if row["result"] in PROBLEM_RESULTS:
                    status.last_problem_at = row["checked_at"]
                if row["checked_at"] >= week_start:
                    status.week["checks"] += 1
                    status.week[row["result"]] += 1
                    status.week_results.append((row["checked_at"], row["result"]))
            status.risk = _risk_percent(rows, now)
        status.recent_problem = status.week[COVER_ONLY] + status.week[BLOCKED] > 0
        status.retry = status.state in PROBLEM_RESULTS or bool(
            status.last_problem_at and status.last_problem_at >= now - RETRY_WINDOW
        )
        statuses[query] = status
    return statuses


def is_retry_target(status):
    """지금 막혔거나 cover 로만 찾히는 곡, 또는 최근 14일 안에 검색이 안 된 적이 있는 곡."""
    return status.retry


def sweep_reserve(calls_per_run):
    """회차마다 반드시 순회하는 곡 수(소수점 버림, 적어도 1곡).

    순회 곡은 거의 다 한 번(기본 검색)에 끝나 곡 수 ≒ 호출 수다.
    """
    return max(1, math.floor(calls_per_run * SWEEP_SHARE))


def _oldest_first(status):
    # 기록이 없는 곡이 맨 앞, 그다음 오래전에 검사한 곡. 같으면 검색어 순이라 같은 기록이면 순서도 같다.
    return (status.checked_at is not None, status.checked_at or datetime.min, status.query)


def budget_allows_another(remaining, pending_covers):
    """기본 검색을 한 곡 더 해도 되는지. 못 찾은 곡마다 cover 검색 한 번씩을 남겨 둔다.

    조건이 `> pending_covers` 이면 이번 곡도 못 찾았을 때 그 곡의 cover 몫이 모자라므로 하나 더 남긴다.
    실제 회차(tasks.run_search_checks)와 다음 회차 범위(run_reach)가 이 규칙 하나를 함께 쓴다.
    """
    return remaining > pending_covers + 1


def run_reach(calls_per_run):
    """한 회차가 기본 검색을 몇 곡까지 하는지: (반드시 하는 곡 수, 많아야 하는 곡 수).

    못 찾은 곡은 cover 검색까지 2회를 쓰므로, 앞에서 검사한 곡이 모두 못 찾히면 가장 적게(30회면 15곡),
    모두 찾히면 가장 많이(29곡) 검사한다. 순서는 select_search_targets 가 미리 정하므로, 다음 회차에
    검사할 곡은 '앞 15곡은 반드시, 그 뒤는 앞 곡들의 결과에 따라 순서대로'로 정확히 말할 수 있다.
    """
    def reach(every_song_fails):
        remaining, pending_covers, songs = calls_per_run, 0, 0
        while budget_allows_another(remaining, pending_covers):
            remaining -= 1
            songs += 1
            pending_covers += every_song_fails
        return songs

    return reach(True), reach(False)


def search_order(statuses, calls_per_run, first=(), skip=()):
    """이번 회차에 검사할 순서와 곡마다 이유: [(status, reason), ...]. 앞에서부터 예산이 허락하는 만큼 검사한다.

    0. 관리자가 '먼저 검사'로 고른 곡(first, 요청한 순서대로)
    1. 순회 몫(sweep_reserve 곡): 재시도 대상이 아닌 곡 가운데 기록이 없거나 가장 오래전에 검사한 곡
    2. 재시도 대상 전부: 가장 오래전에 시도한 곡부터. 예산이 모자라면 남은 곡은 다음 회차에 먼저 온다
    3. 예산이 남으면 나머지 순회 곡

    관리자가 '이번에 빼기'로 고른 곡(skip)은 순서에서 뺀다. 순회 몫을 재시도 앞에 두는 것은 재시도 대상이
    예산보다 많아도 그 몫만큼은 확인하게 하려는 것이다. 위험도는 보지 않는다.
    """
    by_query = {status.query: status for status in statuses}
    requested = [by_query[query] for query in dict.fromkeys(first) if query in by_query and query not in skip]
    taken = {status.query for status in requested} | set(skip)
    rest = [status for status in by_query.values() if status.query not in taken]
    retry = sorted((s for s in rest if is_retry_target(s)), key=_oldest_first)
    sweep = sorted((s for s in rest if not is_retry_target(s)), key=_oldest_first)
    reserved = sweep_reserve(calls_per_run)
    return (
        [(s, REASON_FIRST) for s in requested]
        + [(s, REASON_SWEEP) for s in sweep[:reserved]]
        + [(s, REASON_RETRY) for s in retry]
        + [(s, REASON_SWEEP) for s in sweep[reserved:]]
    )


def select_search_targets(statuses, calls_per_run, first=(), skip=()):
    """search_order 에서 곡만 꺼낸 것."""
    return [status for status, _ in search_order(statuses, calls_per_run, first, skip)]


def last_run(checks, statuses):
    """가장 최근 회차에 검사한 곡과 결과: {"started_at", "songs": [(검색어, 결과), ...]}. 기록이 없으면 None.

    회차는 기록의 회차 시작 시각(run_started_at)으로 묶는다. 지금 목록에 없거나 영상 ID 가 바뀐 곡의
    기록은 다른 대상을 검사한 것이라 뺀다.
    """
    stamped = [row for row in checks if row.get("run_started_at")]
    if not stamped:
        return None
    started_at = max(row["run_started_at"] for row in stamped)
    results = {}
    for row in sorted(stamped, key=lambda r: (r["checked_at"], r.get("id") or 0)):
        status = statuses.get(row["query"])
        if row["run_started_at"] == started_at and status is not None and status.video_id == row["video_id"]:
            results[row["query"]] = row["result"]  # 같은 곡이 두 번 있으면 나중 결과가 남는다
    return {"started_at": started_at, "songs": sorted(results.items())}


def split_requests(requests):
    """search_requests 행을 (먼저 검사할 검색어 목록, 뺄 검색어 집합)으로. 먼저 검사는 요청한 순서를 지킨다."""
    ordered = sorted(requests, key=lambda r: (r["requested_at"], r["query"]))
    first = [r["query"] for r in ordered if r["action"] == REQUEST_FIRST]
    skip = {r["query"] for r in ordered if r["action"] == REQUEST_SKIP}
    return first, skip


def summarize_statuses(statuses):
    """현재 상태별 곡 수, '최근 7일' 탭 곡 수, 최근 7일 안에 한 번이라도 검사한 곡 수, 재시도 대상 수.

    곡 수는 영상 ID 가 있는(검사할 수 있는) 곡만 센다.
    """
    summary = {
        "songs": 0, "checked_in_window": 0, "recent": 0, "retry": 0,
        **{state: 0 for state in (*RESULTS, UNCHECKED)},
    }
    for status in statuses:
        summary["songs"] += 1
        summary[status.state] += 1
        summary["recent"] += status.recent_problem
        summary["retry"] += status.retry
        if status.week["checks"]:
            summary["checked_in_window"] += 1
    return summary
