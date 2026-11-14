import json
import logging
import random
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

try:
    import fcntl
except ImportError:  # 윈도우 개발 환경. 여러 프로세스로 띄울 일이 없다.
    fcntl = None

import requests

from stelline.config import PROJECT_ROOT, SEARCH_API_INTERVAL, SEARCH_API_KEY, TEMP_API_KEY
from stelline.database.connection import database_cursor
from stelline.http_client import SESSION, describe_request_error
from stelline.logging_config import events

from .history import (
    BLOCKED,
    CHECK_RETENTION,
    COVER_ONLY,
    REASON_FIRST,
    REQUEST_ACTIONS,
    VISIBLE,
    budget_allows_another,
    build_statuses,
    cover_query,
    is_retry_target,
    run_reach,
    search_order,
    split_requests,
    utc_now,
)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# 유튜브 검색 결과 페이지에 박혀 있는 JSON 덩어리. 크롤링마다 다시 만들 이유가 없다.
YT_INITIAL_DATA_RE = re.compile(r"ytInitialData\s*=\s*({.*?});", re.DOTALL)

# 한 회차에 부를 수 있는 YouTube 검색 횟수. 하루 회차 수(search_run_hours_kst 의 개수) × 이 값 × 100 단위가
# 하루 9,000 을 넘으면 안 된다. 할당량 10,000 중 1,000 은 같은 프로젝트의 다른 사용분 몫이다
# (config.SEARCH_API_INTERVAL 참고, 테스트가 확인한다). 지금은 3회 × 30 = 90회.
# 몇 곡을 검사할지는 이 예산이 정한다. 기본 검색에서 못 찾은 곡마다 cover 검색을 한 번씩
# 할 수 있게 남겨 두며, history.search_order 가 정한 순서(관리자 요청 포함)대로 검사한다.
# 회차 수나 이 값이 바뀌면 재시도·순회가 얼마나 자주 돌아오는지만 달라지고 판정 기준은 그대로다.
# 하루 90회를 2·3·4·6회로 나눠 본 모의 실험(2026-11)에서 8시간 × 30회가 막힌 곡 재시도가 가장 빨랐다.
SEARCH_CALLS_PER_RUN = 30

# 정기 회차는 UTC 기준 SEARCH_API_INTERVAL 의 배수 시각에 시작한다(wait_until_next_search_interval).
# 화면·관리자 문구의 일정은 모두 아래 함수로 계산한다. 글자로 '8시간'을 적어 두면 간격을 바꿀 때 어긋난다.
# 간격은 하루(24시간)를 나누어떨어지는 시간 단위여야 한다(테스트가 확인한다).


def search_run_hours_kst():
    """정기 회차가 시작하는 한국 시각(시)들. 개수가 곧 하루 회차 수다. 예: 8시간 간격이면 [1, 9, 17]."""
    step_hours = SEARCH_API_INTERVAL // 3600
    return sorted({(hour + 9) % 24 for hour in range(0, 24, step_hours)})


def next_search_run_epoch(now_epoch):
    """다음 정기 회차가 시작하는 시각(epoch 초)."""
    return (int(now_epoch) // SEARCH_API_INTERVAL + 1) * SEARCH_API_INTERVAL

# 검색어 열의 길이. cover 를 붙여 이보다 길어지면 cover 검색을 건너뛴다.
QUERY_MAX_LENGTH = 512

# 회차가 끝나면 운영 기록에 이 말로 시작하는 한 줄을 남긴다. 관리자 화면의 '운영 로그'가
# 이 줄로 마지막 회차를 찾는다(admin/server_logs.py).
SEARCH_EVENT_PREFIX = "검색 점검"
SEARCH_DONE_EVENT = f"{SEARCH_EVENT_PREFIX} 완료"
# 결과는 곡마다 바로 저장하므로 중간에 끊겨도 그때까지 검사한 곡은 남는다.
# '쿼터 초과'는 운영 점검 표(README_DEV)가 찾는 말이라 넣어 둔다.
SEARCH_STOPPED_EVENT = f"{SEARCH_EVENT_PREFIX} 중단(쿼터 초과 등 API 오류, 그때까지 검사한 곡은 저장함)"


def fetch_search_songs():
    """검사 대상 곡 목록. 관리자가 넣은 검색어와 영상 ID 만 읽는다."""
    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT query, video_id FROM song_infos ORDER BY query")
            return cursor.fetchall()
    except Exception:
        logging.exception("검색 점검 곡 목록 불러오기 실패")
        return []


def read_search_checks(cursor, since):
    """since(UTC) 뒤의 검사 기록. 관리자 화면처럼 이미 연결을 연 쪽도 같은 질의를 쓴다."""
    cursor.execute(
        """SELECT id, query, video_id, result, fallback_query, checked_at, run_started_at
             FROM search_checks
            WHERE checked_at >= %s
            ORDER BY checked_at, id""",
        (since,),
    )
    return cursor.fetchall()


def fetch_search_checks(since):
    try:
        with database_cursor() as cursor:
            return read_search_checks(cursor, since)
    except Exception:
        logging.exception("검색 검사 기록 불러오기 실패")
        return []


def read_search_requests(cursor):
    cursor.execute("SELECT query, action, requested_at FROM search_requests ORDER BY requested_at, query")
    return cursor.fetchall()


def fetch_search_requests():
    """관리자가 다음 회차를 조정한 요청. 못 읽으면 조정 없이 돈다(요청은 지워지지 않고 남는다)."""
    try:
        with database_cursor() as cursor:
            return read_search_requests(cursor)
    except Exception:
        logging.exception("다음 검색 조정 요청 불러오기 실패")
        return []


def set_search_request(query, action):
    """다음 회차 조정을 남긴다. 곡마다 하나라 새 요청이 예전 요청을 바꾼다."""
    if action not in REQUEST_ACTIONS:
        raise ValueError(f"모르는 조정: {action}")
    with database_cursor() as cursor:
        cursor.execute(
            """INSERT INTO search_requests (query, action, requested_at) VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE action = VALUES(action), requested_at = VALUES(requested_at)""",
            (query, action, utc_now()),
        )


def clear_search_request(query):
    with database_cursor() as cursor:
        cursor.execute("DELETE FROM search_requests WHERE query = %s", (query,))


def clear_applied_requests(queries, before):
    """이번 회차에 쓴 요청을 지운다. 회차가 돌던 중에 새로 들어온 요청(before 뒤)은 다음 회차 몫이라 남긴다."""
    if not queries:
        return
    try:
        with database_cursor() as cursor:
            cursor.executemany(
                "DELETE FROM search_requests WHERE query = %s AND requested_at <= %s",
                [(query, before) for query in queries],
            )
    except Exception:
        logging.exception("다음 검색 조정 요청 정리 실패")


def load_search_state(now=None):
    """곡 목록, 검사 기록, 관리자 요청, 그리고 곡마다 상태.

    지난 회차에 무엇을 검사했는지는 기록이, 다음 회차 순서는 곡 목록·기록·요청이 다시 필요하다
    (다음 회차가 시작하는 시각 기준으로 상태를 다시 계산한다, plan_next_run).
    """
    now = now or utc_now()
    songs = fetch_search_songs()
    checks = fetch_search_checks(now - CHECK_RETENTION)
    return {
        "songs": songs, "checks": checks, "requests": fetch_search_requests(), "now": now,
        "statuses": build_statuses(songs, checks, now),
    }


def plan_next_run(state):
    """다음 정기 회차가 검사할 순서. 예상이 아니라, 그 회차가 시작할 시각 기준으로 실제 회차와 똑같이 계산한다.

    순서 앞 `sure` 곡은 반드시 검사하고, 그 뒤는 앞 곡들의 결과에 따라(못 찾으면 cover 검색으로 2회씩 쓴다)
    `most` 곡까지 순서대로 검사한다. 그사이 관리자 즉시 실행이나 곡·요청 변경이 있으면 순서도 그에 맞게 바뀐다.
    """
    starts_at = datetime.fromtimestamp(next_search_run_epoch(state["now"].replace(tzinfo=timezone.utc).timestamp()),
                                       timezone.utc).replace(tzinfo=None)
    statuses = build_statuses(state["songs"], state["checks"], starts_at)
    first, skip = split_requests(state["requests"])
    order = search_order(statuses.values(), SEARCH_CALLS_PER_RUN, first, skip)
    sure, most = run_reach(SEARCH_CALLS_PER_RUN)
    return {
        "starts_at": starts_at,
        "order": order[:most],
        "sure": min(sure, len(order)),
        "skipped": sorted(skip & set(statuses)),
    }


def load_song_statuses(now=None):
    """곡마다 현재 상태·최근 7일·재시도 여부. 화면·API·관리자·검색 대상 선정이 모두 이것 하나를 쓴다."""
    state = load_search_state(now)
    return state["statuses"], state["now"]


def record_check(status, result, fallback_query=None, run_started_at=None):
    """곡 하나의 검사 결과를 바로 저장한다. 실패해도 회차는 계속 돈다(그 곡은 다음 회차에 다시 대상).

    run_started_at 은 그 곡을 검사한 회차가 시작한 시각이다. 화면이 '마지막 검색'에서 무엇을
    검사했는지 보여 줄 때 이 값으로 회차를 묶는다.
    """
    try:
        with database_cursor() as cursor:
            cursor.execute(
                """INSERT INTO search_checks (query, video_id, result, fallback_query, checked_at, run_started_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (status.query, status.video_id, result, fallback_query, utc_now(), run_started_at),
            )
        return True
    except Exception:
        logging.exception("검색 검사 결과 저장 실패: %s", status.query)
        return False


def prune_old_checks(now):
    try:
        with database_cursor() as cursor:
            cursor.execute("DELETE FROM search_checks WHERE checked_at < %s", (now - CHECK_RETENTION,))
    except Exception:
        logging.exception("오래된 검색 검사 기록 정리 실패")


def _youtube_video_ids_for_query(query, api_key):
    """YouTube Data API 검색 결과에서 상위 영상 ID 목록을 반환한다."""
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 3,
        "key": api_key,
    }
    response = SESSION.get(YOUTUBE_SEARCH_URL, params=params, timeout=10)
    response.raise_for_status()
    items = response.json().get("items", [])
    return [item["id"]["videoId"] for item in items if "id" in item]


_PAGE_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def describe_search_page(response):
    """결과 JSON 을 못 찾은 검색 페이지가 어떤 페이지였는지 한 줄로 줄인다.

    동의·로봇 확인 페이지로 넘어갔는지(최종 주소), 페이지 제목, 결과 JSON 이름이 아예 없는지 아니면
    다른 모양(문자열로 감싼 JSON 등)으로 있는지를 보면 파서를 고칠지 그냥 둘지 정할 수 있다.
    """
    text = response.text or ""
    parts = [f"HTTP {getattr(response, 'status_code', '?')}"]
    url = getattr(response, "url", None)
    if isinstance(url, str):
        # 검색어가 든 쿼리 문자열은 앞에 이미 적으므로 호스트와 경로만 남긴다.
        where = urlsplit(url)
        parts.append(f"{where.hostname}{where.path}")
    parts.append(f"{len(text)}자")
    title = _PAGE_TITLE_RE.search(text)
    parts.append(f"제목 {' '.join(title.group(1).split())[:60]!r}" if title else "제목 없음")
    marker = text.find("ytInitialData")
    if marker < 0:
        parts.append("ytInitialData 없음")
    else:
        start = marker + len("ytInitialData")
        parts.append(f"ytInitialData 뒤 {text[start:start + 20]!r}")
    return " · ".join(parts)


def find_videos_on_search_page(statuses):
    """API 와 cover 검색에서 못 찾은 곡을 웹 검색 결과 페이지에서 한 번 더 찾는다.

    찾은 곡의 검색어 집합을 돌려준다. 크롤링이 막히거나 결과 JSON 이 없는 페이지가 오면 거기서 멈추고
    그때까지 찾은 것만 돌려준다(못 본 곡은 찾지 못한 것으로 본다).
    """
    found = set()
    base_url = "https://www.youtube.com/results"
    headers = {"User-Agent": "Mozilla/5.0"}

    for status in statuses:
        time.sleep(random.uniform(3, 8))
        try:
            response = SESSION.get(base_url, params={"search_query": status.query}, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            logging.error("크롤링 실패: %s", describe_request_error(exc))
            break
        match = YT_INITIAL_DATA_RE.search(response.text)
        if not match:
            # 결과 JSON 이 없는 페이지는 검색어 탓이 아니라 그때 YouTube 가 다른 모양의 페이지를 준 것이다.
            # 2026-11-14 09시 회차에는 막힌 7곡이 모두 이렇게 실패했고 그 뒤로는 재현되지 않았다. 같은 회차의
            # 다음 곡도 같은 페이지를 받으므로 거기서 멈춘다. 본문이 남지 않아 원인을 알 수 없었으니
            # 어떤 페이지였는지 가늠할 단서를 한 줄 남긴다.
            logging.error("크롤링 데이터 파싱 실패: %s · %s", status.query, describe_search_page(response))
            break
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            logging.error("JSON 파싱 실패: %s", status.query)
            continue

        video_ids = []
        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
        for section in contents:
            for item in section.get("itemSectionRenderer", {}).get("contents", []):
                video = item.get("videoRenderer")
                if video and len(video_ids) < 3:
                    video_ids.append(video["videoId"])
        if status.video_id in video_ids:
            found.add(status.query)

    return found


def summarize_search_run(stats):
    """회차 결과를 관리자 화면에서 한 줄로 읽을 수 있게 줄인다.

    - 재시도 m/n: 재시도 대상 n곡 가운데 이번에 다시 시도한 곡 수. 예산이 모자라면 남은 곡이 다음 회차에 먼저 온다.
    - 끝의 '순회 다음 차례'는 순회 곡 가운데 아직 검사하지 않은 가장 오래된 곡이 며칠 전에 검사됐는지다.
      오래 문제가 없던 곡을 한 바퀴 도는 데 걸리는 기간과 같다.
    """
    if stats["unchecked_left"]:
        upcoming = f"기록 없는 곡 {stats['unchecked_left']}곡 남음"
    elif stats["sweep_wait_days"] is not None:
        upcoming = f"순회 다음 차례는 {stats['sweep_wait_days']:.1f}일 전 검사한 곡"
    else:
        upcoming = "순회할 곡 없음"
    requested = f" · 관리자 요청 {stats['requested_checked']}곡" if stats.get("requested_checked") else ""
    return (
        f"{stats['mode']} · 검사 {stats['checked']}곡"
        f"(정상 {stats[VISIBLE]} · cover로만 {stats[COVER_ONLY]} · 막힘 {stats[BLOCKED]})"
        f"{requested}"
        f" · 재시도 {stats['retry_checked']}/{stats['retry_total']}곡"
        f" · 순회 {stats['sweep_checked']}곡(처음 검사 {stats['first_time']})"
        f" · cover로 찾음 {stats['cover_found']}/{stats['cover_calls']}"
        f" · 크롤링으로 찾음 {stats['crawl_found']}"
        f" · API {stats['calls_used']}/{SEARCH_CALLS_PER_RUN}회"
        f" · {upcoming}"
    )


def _pick_api_key(by_admin):
    if by_admin:
        logging.info("관리자 즉시 검색 실행")
        return TEMP_API_KEY
    if not SEARCH_API_KEY:
        return None
    key_index = random.randrange(len(SEARCH_API_KEY))
    # 키 값 대신 순번만 남긴다. 할당량이 어느 키에서 먼저 바닥나는지는 이것으로 볼 수 있다.
    logging.info("자동 즉시 검색 실행: 검색 키 %s/%s", key_index + 1, len(SEARCH_API_KEY))
    return SEARCH_API_KEY[key_index]


def run_search_checks(by_admin=False):
    """검사 한 회차. 곡마다 결과가 나오는 대로 search_checks 에 바로 남긴다.

    순서: 기본 검색(API) → 못 찾으면 cover 검색(API) → 그래도 못 찾으면 웹 검색 결과 페이지.
    회차 결과를 모아 두었다가 한꺼번에 저장하지 않으므로, 중간에 API 오류가 나도 그때까지
    검사한 곡은 남고, 못 한 곡은 그대로 다음 회차의 대상이 된다.
    """
    stats = {
        "mode": "관리자" if by_admin else "자동",
        "checked": 0, VISIBLE: 0, COVER_ONLY: 0, BLOCKED: 0,
        "requested_checked": 0,
        "retry_total": 0, "retry_checked": 0, "sweep_checked": 0, "first_time": 0,
        "cover_calls": 0, "cover_found": 0, "crawl_found": 0,
        "calls_used": 0, "unchecked_left": 0, "sweep_wait_days": None,
    }
    logging.info("검색 시작")
    api_key = _pick_api_key(by_admin)
    if not api_key:
        logging.error("검색용 YouTube API 키가 설정되지 않았습니다.")
        return {"stats": stats, "error": "검색용 YouTube API 키가 설정되지 않음"}

    state = load_search_state()
    statuses, now = state["statuses"], state["now"]
    if not statuses:
        # DB 가 끊겨도 목록 읽기는 빈 목록을 돌려준다. 그대로 '완료'라고 남기면 아무것도 안 했는데
        # 정상으로 보이므로 경고로 남긴다(관리자 화면 '운영 로그'에 '확인 필요'로 뜬다).
        return {"stats": stats, "error": "검사할 곡을 불러오지 못함(DB 연결 또는 곡 목록 확인)"}
    # 관리자 요청까지 반영한 순서. 화면의 '다음 검색'(plan_next_run)과 같은 함수로 정한다.
    first, skip = split_requests(state["requests"])
    order = search_order(statuses.values(), SEARCH_CALLS_PER_RUN, first, skip)
    reasons = {status.query: reason for status, reason in order}
    targets = [status for status, _ in order]
    stats["retry_total"] = sum(1 for status in targets if is_retry_target(status))
    checked = set()

    # 이 회차의 기록은 모두 회차 시작 시각(now)으로 묶는다. 화면의 '마지막 검색'이 이것으로 회차를 고른다.
    def record(status, result, fallback_query=None):
        if record_check(status, result, fallback_query, run_started_at=now):
            checked.add(status.query)
            stats["checked"] += 1
            stats[result] += 1
            # status 는 이번 검사 전에 계산한 값이라, 고를 때 어느 쪽(요청/재시도/순회)이었는지 그대로 센다.
            if reasons.get(status.query) == REASON_FIRST:
                stats["requested_checked"] += 1
            elif is_retry_target(status):
                stats["retry_checked"] += 1
            else:
                stats["sweep_checked"] += 1
                stats["first_time"] += status.checked_at is None

    failure = ""
    remaining = SEARCH_CALLS_PER_RUN
    missing = []  # 기본 검색에서 못 찾은 곡. cover 검색을 기다린다.
    logging.info("[기본 검색 시작] 곡 %s", len(targets))

    # 못 찾은 곡마다 cover 검색 한 번을 남겨 둔다(history.budget_allows_another — 다음 회차 예상과 같은 규칙).
    queue = list(targets)
    while queue and budget_allows_another(remaining, len(missing)):
        status = queue.pop(0)
        time.sleep(20)
        try:
            logging.info(
                "API 요청 시도 query=%s, video_id=%s, remainingQuotes=%s, not_searched=%s",
                status.query, status.video_id, remaining, len(missing),
            )
            video_ids = _youtube_video_ids_for_query(status.query, api_key)
        except requests.RequestException as exc:
            failure = describe_request_error(exc)
            logging.error("API 요청 실패: %s", failure)
            break
        remaining -= 1
        if status.video_id in video_ids:
            record(status, VISIBLE)
        else:
            missing.append(status)
    logging.info("[기본 검색 종료] remainingQuotes=%s, not_searched=%s", remaining, len(missing))

    still_missing = []
    for index, status in enumerate(missing):
        if failure or remaining <= 0:
            # API 를 더 쓸 수 없으면 남은 곡은 cover 검색 없이 웹 검색만 한다.
            still_missing.extend(missing[index:])
            break
        fallback = cover_query(status.query)
        if len(fallback) > QUERY_MAX_LENGTH:
            still_missing.append(status)
            continue
        time.sleep(20)
        try:
            logging.info(
                "cover 검색 query=%s, video_id=%s, remainingQuotes=%s, not_searched=%s",
                fallback, status.video_id, remaining, len(missing) - index,
            )
            video_ids = _youtube_video_ids_for_query(fallback, api_key)
        except requests.RequestException as exc:
            failure = describe_request_error(exc)
            logging.error("cover 검색 API 요청 실패: %s", failure)
            still_missing.extend(missing[index:])
            break
        remaining -= 1
        stats["cover_calls"] += 1
        if status.video_id in video_ids:
            stats["cover_found"] += 1
            record(status, COVER_ONLY, fallback)
        else:
            still_missing.append(status)
    logging.info("[cover 검색 종료] remainingQuotes=%s, not_searched=%s", remaining, len(still_missing))

    found_on_page = find_videos_on_search_page(still_missing)
    for status in still_missing:
        if status.query in found_on_page:
            stats["crawl_found"] += 1
            record(status, VISIBLE)
        else:
            record(status, BLOCKED)
    logging.info("[최종 결과] 총 실패곡=%s", len(still_missing) - len(found_on_page))

    prune_old_checks(now)
    # 쓴 요청만 지운다. '먼저 검사'는 실제로 검사한 곡만(못 한 곡은 다음 회차에도 맨 앞), '이번에 빼기'는
    # 회차가 실제로 돌았을 때만. 회차 도중 새로 들어온 요청은 다음 회차 몫이라 남긴다(requested_at > now).
    clear_applied_requests(
        [query for query in first if query in checked] + (sorted(skip) if checked else []),
        before=now,
    )
    stats["calls_used"] = SEARCH_CALLS_PER_RUN - remaining
    sweep_left = [s for s in targets if s.query not in checked and not is_retry_target(s)]
    stats["unchecked_left"] = sum(1 for s in sweep_left if s.checked_at is None)
    waited = [now - s.checked_at for s in sweep_left if s.checked_at is not None]
    if waited:
        stats["sweep_wait_days"] = max(waited).total_seconds() / 86400
    return {"stats": stats, "error": failure}


# 검사 한 회차는 API 할당량을 수십 번 쓴다. 정기 검사와 관리자 즉시 검사가 겹치면
# 할당량을 두 번 쓰고 같은 곡을 두 번 검사하므로, 한 번에 한 회차만 돌게 막는다.
#
# 정기 검사는 백그라운드 작업을 맡은 워커 하나에서 돌지만, 관리자 요청은 gunicorn 의
# 어느 워커에나 떨어진다. 그래서 같은 프로세스 안의 스레드 잠금(SEARCH_LOCK)에 더해
# 프로세스끼리 통하는 파일 잠금(SEARCH_LOCK_PATH)을 함께 잡는다.
SEARCH_LOCK = threading.Lock()
SEARCH_LOCK_PATH = PROJECT_ROOT / ".search_cycle.lock"

# 파일 잠금은 파일이 열려 있는 동안만 유지된다. SEARCH_LOCK 을 쥔 스레드만 건드린다.
_search_lock_handle = None


def acquire_search_lock(blocking=True):
    """검사 한 회차를 돌려도 되면 True. blocking=False 면 누가 돌고 있을 때 바로 False."""
    global _search_lock_handle
    if not SEARCH_LOCK.acquire(blocking=blocking):
        return False
    if fcntl is None:
        return True
    try:
        handle = open(SEARCH_LOCK_PATH, "a", encoding="utf-8")
    except OSError:
        # 잠금 파일을 못 만든다고 검사를 통째로 멈추면 그쪽이 더 큰 손해다.
        logging.warning("검색 잠금 파일을 열 수 없어 프로세스 간 잠금 없이 돌립니다: %s", SEARCH_LOCK_PATH)
        return True
    try:
        fcntl.flock(handle, fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        SEARCH_LOCK.release()
        return False
    _search_lock_handle = handle
    return True


def release_search_lock():
    global _search_lock_handle
    handle, _search_lock_handle = _search_lock_handle, None
    if handle is not None:
        handle.close()  # 닫으면 파일 잠금도 풀린다.
    SEARCH_LOCK.release()


def run_search_once(by_admin=False):
    """검사 한 회차를 돌고 운영 기록에 한 줄을 남긴다. 호출하는 쪽이 acquire_search_lock() 을 잡고 있어야 한다."""
    try:
        outcome = run_search_checks(by_admin)
        summary = summarize_search_run(outcome["stats"])
        if outcome["error"]:
            # 경고로 남겨 관리자 화면에 띄운다. 그때까지 검사한 곡의 결과는 이미 저장됐다.
            events.warning("%s: %s · %s", SEARCH_STOPPED_EVENT, outcome["error"], summary)
        else:
            logging.info("검색 데이터 업데이트 완료!")
            events.info("%s: %s", SEARCH_DONE_EVENT, summary)
    except Exception:
        logging.exception("검색 업데이트 오류")


# 주기적으로 검색 데이터 가져오기
def run_search_cycle():
    logging.info("주기적 검색 시작됨")
    while True:
        acquire_search_lock()
        try:
            run_search_once()
        finally:
            release_search_lock()
        wait_until_next_search_interval()


def start_admin_search():
    """관리자 즉시 검사를 띄운다. 이미 한 회차가 돌고 있으면 띄우지 않고 False 를 돌려준다."""
    if not acquire_search_lock(blocking=False):
        return False

    def run():
        try:
            run_search_once(by_admin=True)
        finally:
            release_search_lock()

    threading.Thread(target=run, daemon=True, name="admin-search").start()
    return True


def wait_until_next_search_interval():
    now = time.time()
    time.sleep(next_search_run_epoch(now) - now)


def start_delayed_search(delay):
    time.sleep(delay)
    logging.info("%s초 후 API 검색 시작", delay)
    run_search_cycle()


def start_search_scheduler():
    """다음 검색 주기가 시작될 때까지 기다렸다가 반복 검색을 시작한다."""
    logging.info("검색 스케줄러 초기화 시작")
    now = time.time()
    delay = max(5, next_search_run_epoch(now) - now)
    hours, remainder = divmod(int(delay), 3600)
    minutes, seconds = divmod(remainder, 60)
    logging.info("첫 검색을 %d:%02d:%02d 만큼 지연..", hours, minutes, seconds)
    # 스레드 이름은 로그 줄의 {search} 로 찍힌다. 관리자 화면이 이것으로 어느 작업의 줄인지 가른다.
    threading.Thread(target=start_delayed_search, daemon=True, args=(delay,), name="search").start()
