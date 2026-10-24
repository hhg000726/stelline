"""로그 설정과 관리자 화면 '운영 로그' 탭.

- 키가 로그에 남지 않는지(파일에 쓸 때, 오류를 한 줄로 줄일 때, 화면에 보여 줄 때).
- 7일이 지난 로그가 날짜 기준으로 지워지는지.
- 운영 기록(app_event.log)에 필요한 줄만 쌓이고, 관리자 화면이 그것을 제대로 읽는지.
"""

import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from stelline.admin import server_logs
from stelline.admin.routes import serialize_row
from stelline.apis.search import tasks
from stelline.background_tasks import monitoring
from stelline.http_client import describe_request_error
from stelline.logging_config import (
    LINE_FORMAT,
    RedactingFormatter,
    build_handlers,
    create_log_handler,
    purge_old_logs,
    redact,
)

# 진짜 키처럼 생겼지만 아무 데도 쓸 수 없는 값.
FAKE_KEY = "AIzaSy" + "A" * 33
YOUTUBE_URL = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id=abc&key={FAKE_KEY}"


def _http_error(status, body, url=YOUTUBE_URL):
    response = requests.Response()
    response.status_code = status
    response._content = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    response.url = url
    response.request = requests.Request("GET", url).prepare()
    return requests.HTTPError(f"{status} Client Error: for url: {url}", response=response)


QUOTA_BODY = {
    "error": {
        "code": 403,
        "message": 'The request cannot be completed because you have exceeded your <a href="/youtube/v3/getting-started#quota">quota</a>.',
        "errors": [{"message": "…", "domain": "youtube.quota", "reason": "quotaExceeded"}],
    }
}


# --- 키 가리기 -----------------------------------------------------------

def test_redact_masks_key_parameter_and_bare_google_keys():
    text = redact(f"for url: {YOUTUBE_URL} / 따로 적힌 키 {FAKE_KEY} / Authorization: Bearer abc.def-ghi")
    assert FAKE_KEY not in text
    assert "key=<가림>" in text
    assert "Bearer <가림>" in text
    assert "part=snippet&id=abc" in text  # 키가 아닌 값은 그대로 둔다


def test_formatter_masks_keys_in_the_traceback_too():
    """예전에는 logging.exception 의 예외 문구에 키가 든 주소가 그대로 찍혔다."""
    try:
        raise _http_error(403, QUOTA_BODY)
    except requests.HTTPError:
        record = logging.getLogger("test").makeRecord(
            "test", logging.ERROR, __file__, 1, "조회수 감시 작업 실패", (), sys.exc_info()
        )
    text = RedactingFormatter(LINE_FORMAT).format(record)
    assert "Traceback" in text
    assert FAKE_KEY not in text


def test_log_time_is_korean_time_regardless_of_server_timezone():
    record = logging.makeLogRecord({"msg": "시각 확인", "created": 0, "msecs": 0})
    assert RedactingFormatter(LINE_FORMAT).formatTime(record) == "1970-01-01 09:00:00,000"


# --- 요청 오류를 한 줄로 -------------------------------------------------

def test_describe_request_error_keeps_status_and_reason_but_not_the_url():
    text = describe_request_error(_http_error(403, QUOTA_BODY))
    assert text.startswith("HTTP 403 quotaExceeded (www.googleapis.com): The request cannot be completed")
    assert "<a" not in text  # 설명에 섞여 오는 링크 태그는 떼어 낸다
    assert FAKE_KEY not in text and "key=" not in text


def test_describe_request_error_without_json_body():
    assert describe_request_error(_http_error(502, b"<html>Bad Gateway</html>")) == "HTTP 502 (www.googleapis.com)"


def test_describe_request_error_for_timeouts():
    error = requests.exceptions.ReadTimeout("timed out", request=requests.Request("GET", YOUTUBE_URL).prepare())
    assert describe_request_error(error) == "응답 시간 초과 (www.googleapis.com)"
    assert describe_request_error(requests.Timeout("timed out")) == "시간 초과"


# --- 파일과 보관 기간 ----------------------------------------------------

def test_purge_removes_old_backups_and_empties_files_left_quiet_too_long(tmp_path):
    today = date(2026, 10, 24)
    now = datetime(2026, 10, 24, 12).timestamp()

    def make(name, text="줄\n", age_days=0):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        moment = now - age_days * 86400
        os.utime(path, (moment, moment))
        return path

    expired_backup = make("app_error.log.2026-10-07", age_days=17)
    kept_backup = make("app_info.log.2026-10-17", age_days=7)  # 딱 7일 전은 남긴다
    recent_backup = make("app_warning.log.2026-10-23", age_days=1)
    quiet_current = make("app_error.log", age_days=8)  # 8일 동안 새 줄이 없었다
    busy_current = make("app_info.log", age_days=0)
    unrelated = make("gunicorn.log", "남겨 둘 파일", age_days=100)

    purge_old_logs(str(tmp_path), today=today, now=now)

    assert not expired_backup.exists()
    assert kept_backup.exists() and recent_backup.exists()
    assert quiet_current.exists() and quiet_current.read_text(encoding="utf-8") == ""
    assert busy_current.read_text(encoding="utf-8") == "줄\n"
    assert unrelated.read_text(encoding="utf-8") == "남겨 둘 파일"


def test_rollover_cleans_up_expired_logs(tmp_path):
    """INFO 파일이 날마다 넘어갈 때 오래된 로그도 함께 정리한다."""
    current = tmp_path / "app_info.log"
    current.write_text("2026-01-01 00:00:00,000 [INFO] 예전 줄\n", encoding="utf-8")
    two_days_ago = time.time() - 2 * 86400
    os.utime(current, (two_days_ago, two_days_ago))
    expired = tmp_path / f"app_warning.log.{(date.today() - timedelta(days=30)).isoformat()}"
    expired.write_text("오래된 경고\n", encoding="utf-8")

    handler = create_log_handler(str(tmp_path), "app_info.log", logging.INFO)
    try:
        handler.handle(logging.makeLogRecord({"msg": "새 줄", "levelno": logging.INFO, "levelname": "INFO"}))
    finally:
        handler.close()

    assert not expired.exists()
    assert (tmp_path / f"app_info.log.{date.fromtimestamp(two_days_ago).isoformat()}").exists()
    assert "새 줄" in current.read_text(encoding="utf-8")


def _emit(handlers, name, level, message):
    record = logging.makeLogRecord(
        {"name": name, "levelno": level, "levelname": logging.getLevelName(level), "msg": message}
    )
    for handler in handlers:
        if record.levelno >= handler.level:
            handler.handle(record)


def test_event_log_only_keeps_records_from_the_events_logger(tmp_path):
    handlers = build_handlers(str(tmp_path))
    try:
        _emit(handlers, "stelline.events", logging.INFO, "운영 기록 한 줄")
        _emit(handlers, "root", logging.WARNING, "일반 경고")
        _emit(handlers, "root", logging.INFO, "평범한 INFO")
    finally:
        for handler in handlers:
            handler.close()

    def read(name):
        return (tmp_path / name).read_text(encoding="utf-8")

    assert "운영 기록 한 줄" in read("app_event.log")
    assert "일반 경고" not in read("app_event.log") and "평범한 INFO" not in read("app_event.log")
    assert "일반 경고" in read("app_warning.log")
    assert "운영 기록 한 줄" in read("app_info.log")


def test_the_admin_reader_understands_what_the_handlers_write(tmp_path):
    """쓰는 쪽(logging_config)과 읽는 쪽(server_logs)의 줄 모양이 어긋나면 탭이 텅 빈다."""
    handlers = build_handlers(str(tmp_path))
    try:
        _emit(handlers, "stelline.events", logging.INFO, f"키가 섞인 줄 {YOUTUBE_URL}")
    finally:
        for handler in handlers:
            handler.close()

    [entry] = server_logs.parse_entries((tmp_path / "app_event.log").read_text(encoding="utf-8"))
    assert entry["level"] == "INFO"
    assert entry["thread"] == "MainThread"
    assert entry["message"].startswith("키가 섞인 줄 https://www.googleapis.com/")
    assert FAKE_KEY not in entry["message"]


def test_reader_keeps_old_lines_whose_message_starts_with_brackets():
    [entry] = server_logs.parse_entries("2026-10-24 09:06:45,023 [INFO] [1차 검사 종료] remainingQuotes=10, not_searched=9\n")
    assert entry["thread"] == ""
    assert entry["message"] == "[1차 검사 종료] remainingQuotes=10, not_searched=9"


# --- 운영 로그 요약 ------------------------------------------------------

NOW = datetime(2026, 10, 24, 10, 8)


def _write_sample_logs(log_dir):
    (log_dir / "app_info.log").write_text(
        "2026-10-24 09:58:09,338 [INFO] YouTube 조회수 동기화 완료\n"
        "2026-10-24 10:03:13,883 [INFO] {monitoring} YouTube 조회수 동기화 완료: 영상 320개\n",
        encoding="utf-8",
    )
    # 키를 가리기 전에 남은 예전 형식 줄.
    (log_dir / "app_warning.log.2026-10-23").write_text(
        "2026-10-23 19:00:18,368 [ERROR] 조회수 감시 작업 실패\n"
        "Traceback (most recent call last):\n"
        '  File "monitoring.py", line 57, in get_playlist_videos\n'
        f"requests.exceptions.HTTPError: 403 Client Error: Forbidden for url: {YOUTUBE_URL}\n",
        encoding="utf-8",
    )
    (log_dir / "app_warning.log").write_text(
        "2026-10-10 15:06:45,000 [ERROR] API 요청 실패: 오래되어 빠져야 하는 줄\n"
        "2026-10-24 09:00:40,000 [ERROR] {search} API 요청 실패: HTTP 429 rateLimitExceeded (www.googleapis.com)\n"
        "2026-10-24 09:01:00,000 [ERROR] {search} API 요청 실패: HTTP 429 rateLimitExceeded (www.googleapis.com)\n",
        encoding="utf-8",
    )
    (log_dir / "app_event.log").write_text(
        "2026-10-24 01:10:10,000 [INFO] {search} 검색 점검 완료: 자동 · 우선 대상 15/15곡(실패 8) · 최종 실패 3곡\n"
        "2026-10-24 09:10:41,000 [INFO] {search} 검색 점검 완료: 자동 · 우선 대상 15/15곡(실패 9) · 최종 실패 4곡\n"
        "2026-10-24 10:07:00,180 [INFO] {MainThread} 관리자 로그인 성공: username=admin\n",
        encoding="utf-8",
    )


def test_overview_reports_task_state_grouped_problems_and_events(tmp_path):
    _write_sample_logs(tmp_path)
    overview = server_logs.build_overview(str(tmp_path), now=NOW)

    monitoring_task, search_task = overview["tasks"]
    assert monitoring_task["state"] == "ok"
    assert monitoring_task["lines"][0] == "마지막 동기화: 10/24 10:03 (4분 전)"
    assert monitoring_task["lines"][1] == (
        "마지막 실패: 10/23 19:00 (15시간 전) — requests.exceptions.HTTPError: 403 Client Error: Forbidden for url: www.googleapis.com"
    )

    assert search_task["state"] == "ok"
    assert "검색 점검 완료: 자동 · 우선 대상 15/15곡(실패 9) · 최종 실패 4곡" in search_task["lines"]
    assert search_task["lines"][-1] == "다음 회차: 10/24 17:00 (6시간 52분 뒤)"

    first, second = overview["problems"]
    assert first["message"] == "API 요청 실패: HTTP 429 rateLimitExceeded (www.googleapis.com)"
    assert first["count"] == 2 and first["thread"] == "검색 점검" and first["is_error"]
    assert second["message"] == "조회수 감시 작업 실패"
    assert overview["problem_count_24h"] == 3  # 7일보다 오래된 10/10 줄은 빠진다

    assert [event["message"] for event in overview["events"]][0] == "관리자 로그인 성공: username=admin"
    assert FAKE_KEY not in json.dumps(overview, default=str, ensure_ascii=False)


def test_overview_flags_a_stalled_monitor_and_a_skipped_search(tmp_path):
    (tmp_path / "app_info.log").write_text(
        "2026-10-24 09:00:00,000 [INFO] {monitoring} YouTube 조회수 동기화 완료: 영상 320개\n", encoding="utf-8"
    )
    (tmp_path / "app_event.log").write_text(
        "2026-10-24 09:09:00,000 [WARNING] {search} 검색 점검 결과 저장 안 함(쿼터 초과 등 API 오류): HTTP 429 rateLimitExceeded (www.googleapis.com)\n",
        encoding="utf-8",
    )
    monitoring_task, search_task = server_logs.build_overview(str(tmp_path), now=NOW)["tasks"]
    assert monitoring_task["state"] == "late"
    assert search_task["state"] == "warn"


def test_overview_falls_back_to_the_old_search_line_right_after_deploy(tmp_path):
    (tmp_path / "app_info.log").write_text(
        "2026-10-24 09:10:41,044 [INFO] 검색 데이터 업데이트 완료!\n", encoding="utf-8"
    )
    _, search_task = server_logs.build_overview(str(tmp_path), now=NOW)["tasks"]
    assert search_task["state"] == "ok"
    assert search_task["lines"][0] == "마지막 회차: 10/24 09:10 (57분 전)"


def test_overview_of_an_empty_log_folder(tmp_path):
    overview = server_logs.build_overview(str(tmp_path / "없는 폴더"), now=NOW)
    assert [task["state"] for task in overview["tasks"]] == ["unknown", "unknown"]
    assert overview["problems"] == [] and overview["events"] == []


# --- 관리자 화면 ---------------------------------------------------------

def _admin_page(admin_client, log_dir):
    with patch("stelline.admin.routes.get_connection"), \
         patch("stelline.admin.routes.load_table", return_value=[]), \
         patch.object(server_logs, "LOG_DIR", str(log_dir)):
        return admin_client.get("/admin/").get_data(as_text=True)


def test_admin_page_has_a_logs_tab(admin_client, tmp_path):
    _write_sample_logs(tmp_path)
    html = _admin_page(admin_client, tmp_path)
    assert 'data-group="logs"' in html and 'data-group-panel="logs"' in html
    assert "작업 상태" in html and "조회수 감시" in html and "검색 점검" in html
    assert "API 요청 실패: HTTP 429 rateLimitExceeded (www.googleapis.com)" in html
    assert "관리자 로그인 성공: username=admin" in html
    assert FAKE_KEY not in html


def test_admin_page_still_opens_when_logs_cannot_be_read(admin_client):
    with patch("stelline.admin.routes.get_connection"), \
         patch("stelline.admin.routes.load_table", return_value=[]), \
         patch("stelline.admin.routes.build_overview", side_effect=OSError("읽기 실패")):
        html = admin_client.get("/admin/").get_data(as_text=True)
    assert "서버 로그를 읽지 못했습니다" in html
    assert 'data-group="karaoke"' in html  # 나머지 관리 화면은 그대로


def _event_messages(caplog):
    return [record.getMessage() for record in caplog.records if record.name == "stelline.events"]


def test_admin_changes_are_recorded_as_events(admin_client, caplog):
    with patch("stelline.admin.routes.get_connection", return_value=MagicMock()), \
         caplog.at_level(logging.INFO, logger="stelline.events"):
        admin_client.post("/admin/data/song_infos", data={
            "csrf_token": admin_client.csrf, "query": "후야 letters to me", "video_id": "abc", "risk": "0",
        })
    assert "관리자 데이터 추가: 검색 점검 곡 — 후야 letters to me" in _event_messages(caplog)


def test_deleting_a_user_report_does_not_copy_its_text_into_the_log(admin_client, caplog):
    token = serialize_row({"id": 7, "content": "사용자가 쓴 제보 내용", "created_at": "2026-10-24 09:00:00"})
    with patch("stelline.admin.routes.get_connection", return_value=MagicMock()), \
         caplog.at_level(logging.INFO, logger="stelline.events"):
        admin_client.post("/admin/data/song_reports/delete", data={"csrf_token": admin_client.csrf, "row_token": token})
    assert _event_messages(caplog) == ["관리자 데이터 삭제: 누락 노래 제보"]


def test_failed_admin_login_is_a_warning_event(client, caplog):
    with caplog.at_level(logging.INFO, logger="stelline.events"):
        client.post("/auth/login", data={"username": "누군가", "password": "틀린 비밀번호"})
    [record] = [r for r in caplog.records if r.name == "stelline.events"]
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "관리자 로그인 실패: username=누군가"
    assert "틀린 비밀번호" not in caplog.text


# --- 백그라운드 작업이 남기는 줄 ------------------------------------------

def test_monitoring_failure_is_one_line_without_the_key(caplog):
    @contextmanager
    def fake_cursor():
        yield MagicMock()

    with patch.object(monitoring, "database_cursor", fake_cursor), \
         patch.object(monitoring, "remove_expired_data"), \
         patch.object(monitoring, "get_playlist_videos", side_effect=_http_error(403, QUOTA_BODY)), \
         patch.object(monitoring.time, "sleep", side_effect=StopIteration), \
         caplog.at_level(logging.INFO):
        with pytest.raises(StopIteration):
            monitoring.monitoring_process()

    assert "조회수 감시 작업 실패: HTTP 403 quotaExceeded (www.googleapis.com)" in caplog.text
    assert FAKE_KEY not in caplog.text


def test_search_run_counts_what_it_checked():
    songs = [
        {"query": "우선 곡", "video_id": "p", "risk": 28},
        {"query": "위험도 0 곡", "video_id": "z", "risk": 0},
    ]
    with patch.object(tasks, "fetch_song_infos_from_db", return_value=songs), \
         patch.object(tasks, "SEARCH_API_KEY", ["key"]), \
         patch.object(tasks, "update_song_risk"), \
         patch.object(tasks, "update_fallback_query", return_value=True), \
         patch.object(tasks, "crawl_search_results_for_missing_videos", side_effect=lambda found: found), \
         patch.object(tasks.time, "sleep"), \
         patch.object(tasks, "_youtube_video_ids_for_query", side_effect=[[], ["z"], ["p"]]):
        result = tasks.search_unverified_songs()

    assert tasks.summarize_search_run(result["stats"]) == (
        "자동 · 우선 대상 1/1곡(실패 1) · 위험도 0 곡 1곡(실패 0) · cover로 찾음 1/1"
        f" · 크롤링으로 찾음 0 · 최종 실패 0곡 · API 3/{tasks.SEARCH_CALLS_PER_RUN}회"
    )


def _run_once(new_songs):
    with patch.object(tasks, "search_unverified_songs", return_value=new_songs), \
         patch.object(tasks, "write_last_search_timestamp"), \
         patch.object(tasks, "save_search_results_to_db") as save:
        tasks.run_search_once()
    return save


STATS = {
    "mode": "자동", "priority_total": 15, "priority_checked": 15, "priority_failed": 9,
    "zero_checked": 5, "zero_failed": 0, "cover_calls": 9, "cover_found": 1, "crawl_found": 4,
    "final_failed": 4, "calls_used": 29,
}


def test_search_run_leaves_one_summary_event(caplog):
    with caplog.at_level(logging.INFO):
        save = _run_once({"all_songs": [], "searched_time": 1.0, "isQuotaExceeded": False, "error": "", "stats": STATS})
    save.assert_called_once()
    assert "검색 데이터 업데이트 완료!" in caplog.text  # 운영 점검 표가 찾는 줄은 그대로 둔다
    assert _event_messages(caplog) == [
        "검색 점검 완료: 자동 · 우선 대상 15/15곡(실패 9) · 위험도 0 곡 5곡(실패 0) · cover로 찾음 1/9"
        f" · 크롤링으로 찾음 4 · 최종 실패 4곡 · API 29/{tasks.SEARCH_CALLS_PER_RUN}회"
    ]


def test_search_run_cut_short_by_the_api_is_a_warning_with_the_reason(caplog):
    with caplog.at_level(logging.INFO):
        save = _run_once({
            "all_songs": [], "searched_time": 1.0, "isQuotaExceeded": True,
            "error": "HTTP 429 rateLimitExceeded (www.googleapis.com)", "stats": STATS,
        })
    save.assert_not_called()
    [record] = [r for r in caplog.records if r.name == "stelline.events"]
    assert record.levelno == logging.WARNING
    assert record.getMessage().startswith(
        "검색 점검 결과 저장 안 함(쿼터 초과 등 API 오류): HTTP 429 rateLimitExceeded (www.googleapis.com) · 자동 · 우선 대상"
    )
