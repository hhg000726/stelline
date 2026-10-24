"""관리자 화면 '운영 로그' 탭에 보여 줄 내용을 로그 파일에서 추린다.

서버에 들어가지 않고도 "제대로 돌고 있나"를 확인하려는 화면이다. 세 가지만 보여 준다.

- 작업 상태: 조회수 감시가 제때 돌고 있는지, 마지막 검색 점검이 어땠고 다음 회차는 언제인지.
- 오류·경고: 최근 7일의 경고 이상을 같은 문구끼리 묶어 횟수와 마지막 시각으로.
- 운영 기록: `events` 로거로 남긴 일(검색 점검 결과, 관리자 작업, 달성 알림, 제보, 서버 시작).

로그 파일만 읽으므로 DB가 죽어 있어도 열린다. 키를 가리기 전에 쓴 예전 줄이 남아 있을 수 있어,
보여 주기 전에 한 번 더 가린다.
"""

import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from stelline.apis.search.tasks import SEARCH_EVENT_PREFIX
from stelline.background_tasks.monitoring import SYNC_DONE_MESSAGE, SYNC_FAILED_MESSAGE
from stelline.config import API_CHECK_INTERVAL, SEARCH_API_INTERVAL
from stelline.logging_config import EVENT_LOG_FILE, INFO_LOG_FILE, LOG_DIR, LOG_KEEP_DAYS, WARNING_LOG_FILE, redact

KST = timezone(timedelta(hours=9))

# `시각 [수준] {스레드} 내용`. 스레드 칸은 나중에 붙였으므로, 그 칸이 없는 예전 줄도 읽는다.
LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3} \[([A-Z]+)\] (?:\{([^}]*)\} )?(.*)$")
# 가린 키(`key=<가림>`)까지 주소의 일부로 본다. 거기서 끊으면 호스트 뒤에 `<가림>`만 남는다.
URL_RE = re.compile(r"https?://[^\s'\"]+")

# 백그라운드 작업 스레드 이름 → 화면에 보일 이름. 요청을 처리한 줄에는 붙이지 않는다.
THREAD_LABELS = {
    "monitoring": "조회수 감시",
    "search": "검색 점검",
    "admin-search": "검색 점검",
    "bugs-rank": "Bugs 순위",
}

STATE_LABELS = {
    "ok": "정상",
    "late": "늦어짐",
    "error": "실패 중",
    "warn": "확인 필요",
    "unknown": "기록 없음",
}

MAX_PROBLEM_GROUPS = 30
MAX_EVENTS = 100
# 조회수 감시는 5분마다 돈다. 세 번 연달아 소식이 없으면 '늦어짐'으로 본다.
MONITORING_LATE_AFTER = timedelta(seconds=API_CHECK_INTERVAL * 3)
# 검색 점검은 8시간마다 돌고 한 회차에 10분 남짓 걸린다. 넉넉히 30분을 더 기다린다.
SEARCH_LATE_AFTER = timedelta(seconds=SEARCH_API_INTERVAL, minutes=30)
# INFO 파일에서는 마지막 동기화 줄만 찾으면 되므로 끝부분만 읽는다.
INFO_TAIL_BYTES = 256 * 1024
# 운영 기록 파일이 생기기 전에 쓰던, 검색 점검 회차의 끝 줄.
LEGACY_SEARCH_DONE = "검색 데이터 업데이트 완료!"
LEGACY_SEARCH_SKIPPED = "쿼터 초과"


def _log_paths(log_dir, name):
    """한 로그의 파일들을 오래된 것부터 돌려준다: 넘긴 파일(이름의 날짜순), 그다음 지금 쓰는 파일."""
    try:
        names = set(os.listdir(log_dir))
    except OSError:
        return []
    backup = re.compile(re.escape(name) + r"\.\d{4}-\d{2}-\d{2}")
    paths = [os.path.join(log_dir, entry) for entry in sorted(n for n in names if backup.fullmatch(n))]
    if name in names:
        paths.append(os.path.join(log_dir, name))
    return paths


def _read_text(path, tail_bytes=None):
    try:
        with open(path, "rb") as handle:
            if tail_bytes:
                size = handle.seek(0, os.SEEK_END)
                handle.seek(max(0, size - tail_bytes))
                if size > tail_bytes:
                    handle.readline()  # 중간에서 잘린 첫 줄은 버린다.
            data = handle.read()
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def parse_entries(text):
    """로그 글을 항목 목록으로 바꾼다. 시각으로 시작하지 않는 줄(예외 내용 등)은 앞 항목에 붙인다."""
    entries = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        match = LINE_RE.match(line)
        if match:
            stamp, level, thread, message = match.groups()
            entries.append({
                "time": datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S"),
                "level": level,
                "thread": thread or "",
                "message": redact(message),
                "detail": [],
            })
        elif entries and line.strip():
            entries[-1]["detail"].append(redact(line))
    return entries


def _read_entries(paths, since, tail_bytes=None):
    entries = []
    for path in paths:
        entries.extend(entry for entry in parse_entries(_read_text(path, tail_bytes)) if entry["time"] >= since)
    entries.sort(key=lambda entry: entry["time"])
    return entries


def _short_urls(text):
    # 주소는 호스트만 남긴다. 예전 줄은 주소에 든 검색어가 달라, 같은 오류가 따로따로 묶였다.
    return URL_RE.sub(lambda match: urlsplit(match.group()).hostname or "주소", text)


def _ago(delta):
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "방금"
    if minutes < 60:
        return f"{minutes}분 전"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}시간 전"
    return f"{hours // 24}일 전"


def _until(delta):
    hours, minutes = divmod(max(0, int(delta.total_seconds() // 60)), 60)
    return f"{hours}시간 {minutes}분 뒤" if hours else f"{minutes}분 뒤"


def _when(moment, now):
    return f"{moment:%m/%d %H:%M} ({_ago(now - moment)})"


def _group_problems(entries, now):
    groups = {}
    for entry in entries:
        key = (entry["level"], _short_urls(entry["message"]))
        group = groups.setdefault(key, {"level": entry["level"], "message": key[1], "count": 0, "first": entry["time"]})
        group["count"] += 1
        # 자세한 내용은 가장 최근 것을 보여 준다.
        group["last"] = entry["time"]
        group["thread"] = THREAD_LABELS.get(entry["thread"], "")
        group["detail"] = "\n".join(entry["detail"])
    ordered = sorted(groups.values(), key=lambda group: group["last"], reverse=True)[:MAX_PROBLEM_GROUPS]
    return [
        {
            **group,
            "is_error": group["level"] in ("ERROR", "CRITICAL"),
            "first_text": f"{group['first']:%m/%d %H:%M}",
            "last_text": _when(group["last"], now),
        }
        for group in ordered
    ]


def _failure_reason(entry):
    """'조회수 감시 작업 실패: HTTP 403 …' 에서 뒷부분만. 예전 줄은 예외 마지막 줄에서 꺼낸다."""
    reason = entry["message"][len(SYNC_FAILED_MESSAGE):].lstrip(": ")
    if not reason and entry["detail"]:
        reason = _short_urls(entry["detail"][-1].strip())
    return reason[:160]


def _monitoring_status(info_entries, problems, now):
    last_ok = max((e["time"] for e in info_entries if e["message"].startswith(SYNC_DONE_MESSAGE)), default=None)
    failures = [e for e in problems if e["message"].startswith(SYNC_FAILED_MESSAGE)]
    last_failure = failures[-1] if failures else None

    lines = [f"마지막 동기화: {_when(last_ok, now) if last_ok else '기록 없음'}"]
    if last_failure:
        reason = _failure_reason(last_failure)
        lines.append(f"마지막 실패: {_when(last_failure['time'], now)}{' — ' + reason if reason else ''}")
    recent_failures = sum(1 for e in failures if e["time"] >= now - timedelta(days=1))
    if recent_failures:
        lines.append(f"최근 24시간 실패 {recent_failures}회")

    if last_ok is None:
        state = "unknown"
    elif last_failure and last_failure["time"] > last_ok:
        state = "error"
    elif now - last_ok > MONITORING_LATE_AFTER:
        state = "late"
    else:
        state = "ok"
    return {
        "key": "monitoring",
        "label": "조회수 감시",
        "schedule": "5분마다 YouTube 조회수를 읽고, 10만 단위를 넘긴 곡은 알림을 보냅니다.",
        "state": state,
        "state_label": STATE_LABELS[state],
        "lines": lines,
    }


def next_search_run(now):
    """다음 검색 점검 시각(한국 시간). 회차는 UTC 기준 8시간 경계에서 시작한다(tasks.wait_until_next_search_interval)."""
    seconds = int(now.replace(tzinfo=KST).timestamp())
    upcoming = (seconds // SEARCH_API_INTERVAL + 1) * SEARCH_API_INTERVAL
    return datetime.fromtimestamp(upcoming, KST).replace(tzinfo=None)


def _search_status(event_entries, info_entries, now):
    runs = [e for e in event_entries if e["message"].startswith(SEARCH_EVENT_PREFIX)]
    if runs:
        last = runs[-1]
        saved = last["level"] == "INFO"
        summary = last["message"]
    else:
        # 배포 직후처럼 운영 기록에 아직 회차가 없으면 예전 끝 줄로 판단한다.
        legacy = [e for e in info_entries if e["message"] in (LEGACY_SEARCH_DONE, LEGACY_SEARCH_SKIPPED)]
        last = legacy[-1] if legacy else None
        saved = bool(last) and last["message"] == LEGACY_SEARCH_DONE
        summary = "결과를 저장했습니다." if saved else "쿼터 초과로 결과를 저장하지 않았습니다."

    upcoming = next_search_run(now)
    lines = []
    if last:
        lines.append(f"마지막 회차: {_when(last['time'], now)}")
        lines.append(summary)
    else:
        lines.append(f"최근 {LOG_KEEP_DAYS}일 안에 끝난 회차가 없습니다.")
    lines.append(f"다음 회차: {upcoming:%m/%d %H:%M} ({_until(upcoming - now)})")

    if last is None:
        state = "unknown"
    elif not saved:
        state = "warn"
    elif now - last["time"] > SEARCH_LATE_AFTER:
        state = "late"
    else:
        state = "ok"
    return {
        "key": "search",
        "label": "검색 점검",
        "schedule": "한국 시간 01·09·17시에 우선 대상 15곡과 위험도 0 곡 일부를 YouTube에서 찾아봅니다.",
        "state": state,
        "state_label": STATE_LABELS[state],
        "lines": lines,
    }


def build_overview(log_dir=None, now=None):
    """'운영 로그' 탭 한 장에 필요한 것을 모은다. 시각은 모두 한국 시간이다."""
    log_dir = log_dir or LOG_DIR
    now = now or datetime.now(KST).replace(tzinfo=None)
    since = now - timedelta(days=LOG_KEEP_DAYS)

    problems = _read_entries(_log_paths(log_dir, WARNING_LOG_FILE), since)
    event_entries = _read_entries(_log_paths(log_dir, EVENT_LOG_FILE), since)
    # 최근 두 파일의 끝부분만 본다. 자정 직후 새 파일이 비어 있어도 마지막 동기화를 찾는다.
    info_entries = _read_entries(_log_paths(log_dir, INFO_LOG_FILE)[-2:], since, tail_bytes=INFO_TAIL_BYTES)

    return {
        "window_days": LOG_KEEP_DAYS,
        "tasks": [
            _monitoring_status(info_entries, problems, now),
            _search_status(event_entries, info_entries, now),
        ],
        "problems": _group_problems(problems, now),
        "problem_count_24h": sum(1 for e in problems if e["time"] >= now - timedelta(days=1)),
        "events": [
            {
                "time_text": f"{entry['time']:%m/%d %H:%M}",
                "ago": _ago(now - entry["time"]),
                "is_warning": entry["level"] != "INFO",
                "thread": THREAD_LABELS.get(entry["thread"], ""),
                "message": entry["message"],
            }
            for entry in reversed(event_entries[-MAX_EVENTS:])
        ],
    }
