"""검색 노출 판정(stelline/apis/search/history.py)과 검사 한 회차의 순수 로직 테스트.

모든 판정은 검사 기록과 '지금' 시각만으로 정해진다. 시각을 고정해 두고, 기록을 바꿔 가며
현재 상태·최근 7일·검색 대상이 각자의 기준대로 나오는지 본다.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import requests

from stelline.apis.search import history, tasks
from stelline.apis.search.history import (
    BLOCKED,
    COVER_ONLY,
    UNCHECKED,
    VISIBLE,
    SongStatus,
    build_statuses,
    select_search_targets,
    summarize_statuses,
    sweep_reserve,
)

NOW = datetime(2026, 11, 7, 3, 0)


def _ago(**delta):
    return NOW - timedelta(**delta)


def _check(query, result, at, video_id=None, fallback_query=None, row_id=0):
    return {
        "id": row_id, "query": query, "video_id": video_id or f"v-{query}", "result": result,
        "fallback_query": fallback_query, "checked_at": at,
    }


def _song(query, video_id=None):
    return {"query": query, "video_id": video_id or f"v-{query}"}


def _status(query, checks, video_id=None):
    return build_statuses([_song(query, video_id)], checks, NOW)[query]


# --- 현재 상태: 가장 최근 검사 결과 ------------------------------------------

def test_current_state_is_the_latest_result_whichever_run_checked_it():
    """예전에는 마지막 회차에서 검사하지 않은 곡이 '지금 막힘'에서 빠졌다. 이제는 곡마다 마지막 결과다."""
    status = _status("곡", [
        _check("곡", VISIBLE, _ago(days=2)),
        _check("곡", BLOCKED, _ago(hours=16)),  # 두 회차 전에 검사하고 그 뒤로는 차례가 안 왔다
    ])
    assert status.state == BLOCKED
    assert status.checked_at == _ago(hours=16)


def test_a_song_without_any_record_is_unchecked():
    status = _status("새 곡", [])
    assert (status.state, status.recent_problem, status.retry, status.checked_at) == (UNCHECKED, False, False, None)


def test_records_for_another_video_do_not_count():
    """관리자가 영상 ID 를 바꾸면 예전 결과는 다른 영상을 찾은 것이다."""
    status = _status("곡", [_check("곡", BLOCKED, _ago(hours=1), video_id="옛 영상")], video_id="새 영상")
    assert status.state == UNCHECKED


def test_cover_only_remembers_the_query_that_found_it():
    status = _status("토아 제육감", [_check("토아 제육감", COVER_ONLY, _ago(hours=3), fallback_query="토아 제육감 cover")])
    assert status.state == COVER_ONLY
    assert status.fallback_query == "토아 제육감 cover"


def test_a_visible_latest_result_drops_the_cover_query():
    status = _status("곡", [
        _check("곡", COVER_ONLY, _ago(days=1), fallback_query="곡 cover"),
        _check("곡", VISIBLE, _ago(hours=8)),
    ])
    assert status.state == VISIBLE and status.fallback_query is None


def test_ties_at_the_same_second_follow_the_insert_order():
    status = _status("곡", [
        _check("곡", VISIBLE, _ago(hours=1), row_id=2),
        _check("곡", BLOCKED, _ago(hours=1), row_id=1),
    ])
    assert status.state == VISIBLE


def test_unknown_results_and_songs_without_video_are_ignored():
    statuses = build_statuses(
        [_song("곡"), {"query": "영상 없음", "video_id": None}],
        [_check("곡", "weird", _ago(hours=1))],
        NOW,
    )
    assert list(statuses) == ["곡"]
    assert statuses["곡"].state == UNCHECKED


# --- 최근 7일: 지금 시각에서 거꾸로 7일 ---------------------------------------

def test_week_counts_only_the_last_seven_days():
    status = _status("곡", [
        _check("곡", BLOCKED, _ago(days=7, hours=1)),   # 7일이 넘었다
        _check("곡", BLOCKED, _ago(days=6, hours=23)),
        _check("곡", COVER_ONLY, _ago(days=3)),
        _check("곡", VISIBLE, _ago(hours=8)),
    ])
    assert status.week == {"checks": 3, VISIBLE: 1, COVER_ONLY: 1, BLOCKED: 1}
    assert [result for _, result in status.week_results] == [BLOCKED, COVER_ONLY, VISIBLE]
    assert status.last_problem_at == _ago(days=3)


def test_a_failure_this_week_keeps_a_visible_song_in_the_recent_tab():
    """'최근 7일' 탭은 지난 7일을, '지금 막힘' 탭은 지금을 본다. 지금 보이는 곡도 7일 안에 막혔으면 최근 7일에 나온다."""
    status = _status("곡", [_check("곡", BLOCKED, _ago(days=2)), _check("곡", VISIBLE, _ago(hours=8))])
    assert (status.state, status.recent_problem) == (VISIBLE, True)


def test_cover_only_counts_as_a_recent_problem():
    status = _status("곡", [_check("곡", COVER_ONLY, _ago(days=3), fallback_query="곡 cover"), _check("곡", VISIBLE, _ago(days=1))])
    assert status.recent_problem is True


def test_a_song_blocked_now_is_also_a_recent_problem():
    status = _status("곡", [_check("곡", BLOCKED, _ago(hours=8))])
    assert (status.state, status.recent_problem) == (BLOCKED, True)


def test_a_failure_older_than_seven_days_leaves_the_screen_but_is_still_retried():
    """화면의 '최근 회복'은 7일, 재시도는 14일. 두 기준은 따로 움직인다."""
    status = _status("곡", [_check("곡", BLOCKED, _ago(days=8)), _check("곡", VISIBLE, _ago(days=1))])
    assert (status.state, status.recent_problem) == (VISIBLE, False)
    assert status.week[BLOCKED] == 0
    assert status.last_problem_at == _ago(days=8)
    assert status.retry is True


def test_a_failure_older_than_the_retry_window_is_no_longer_retried():
    status = _status("곡", [_check("곡", BLOCKED, _ago(days=15)), _check("곡", VISIBLE, _ago(days=1))])
    assert (status.recent_problem, status.retry) == (False, False)


def test_the_window_moves_with_now_not_with_the_number_of_checks():
    """하루 회차 수가 바뀌어도 '7일'의 뜻이 그대로다. 검사가 몇 번이었든 시각으로만 자른다."""
    sparse = [_check("곡", BLOCKED, _ago(days=6))]
    dense = [_check("곡", BLOCKED, _ago(days=6))] + [
        _check("곡", VISIBLE, _ago(hours=hours)) for hours in range(4, 140, 4)
    ]
    assert _status("곡", sparse).last_problem_at == _status("곡", dense).last_problem_at == _ago(days=6)


# --- 검색 대상: 최근 실패한 곡을 우선 다시 시도 ------------------------------------

def _statuses(spec):
    """spec: {검색어: [(결과, 몇 시간 전), ...]}"""
    songs = [_song(query) for query in spec]
    checks = [_check(query, result, _ago(hours=hours)) for query, rows in spec.items() for result, hours in rows]
    return build_statuses(songs, checks, NOW)


def test_recently_failed_songs_are_retry_targets():
    statuses = _statuses({
        "막힘": [(BLOCKED, 8)],
        "cover로만": [(COVER_ONLY, 8)],
        "최근 회복": [(BLOCKED, 48), (VISIBLE, 8)],
        "열흘 전 실패": [(BLOCKED, 24 * 10), (VISIBLE, 24 * 5)],
        "보름 전 실패": [(BLOCKED, 24 * 15), (VISIBLE, 24 * 5)],
        "늘 정상": [(VISIBLE, 24 * 3)],
        "기록 없음": [],
    })
    assert {q for q, s in statuses.items() if history.is_retry_target(s)} == {"막힘", "cover로만", "최근 회복", "열흘 전 실패"}
    assert statuses["열흘 전 실패"].recent_problem is False  # 화면의 '최근 7일'에는 안 나오지만 재시도는 한다


def test_targets_reserve_a_sweep_share_then_retry_everything_recent():
    spec = {f"막힘{i:02d}": [(BLOCKED, 8 + i)] for i in range(10)}
    spec.update({f"정상{i:02d}": [(VISIBLE, 24 * (20 - i))] for i in range(10)})
    spec["새 곡"] = []
    order = [s.query for s in select_search_targets(_statuses(spec).values(), calls_per_run=30)]

    reserved = sweep_reserve(30)
    assert reserved == 4
    # 1) 순회 몫: 기록 없는 곡, 그다음 가장 오래전에 검사한 정상 곡
    assert order[:reserved] == ["새 곡", "정상00", "정상01", "정상02"]
    # 2) 재시도 대상 전부: 가장 오래전에 시도한 곡부터
    assert order[reserved:reserved + 10] == [f"막힘{i:02d}" for i in range(9, -1, -1)]
    # 3) 남은 순회 곡
    assert order[reserved + 10:] == [f"정상{i:02d}" for i in range(3, 10)]


def test_selection_ignores_the_old_risk_column():
    songs = [{**_song("a"), "risk": 28}, {**_song("b"), "risk": 0}]
    checks = [_check("a", VISIBLE, _ago(days=9)), _check("b", BLOCKED, _ago(hours=8))]
    order = [s.query for s in select_search_targets(build_statuses(songs, checks, NOW).values(), 2)]
    assert order == ["a", "b"]  # a 는 순회 몫(1곡), b 는 재시도. 옛 위험도 28 은 아무 뜻이 없다.


def test_the_sweep_share_follows_the_budget():
    """예산을 바꾸면 순회 몫도 따라 바뀐다(소수점 버림, 적어도 1곡)."""
    assert sweep_reserve(30) == 4
    assert sweep_reserve(40) == 6
    assert sweep_reserve(60) == 9
    assert sweep_reserve(3) == 1


def test_summary_counts_states_and_the_recent_tab():
    statuses = _statuses({
        "막힘": [(BLOCKED, 8)],
        "cover로만": [(COVER_ONLY, 8)],
        "최근 회복": [(BLOCKED, 48), (VISIBLE, 8)],
        "오래 정상": [(VISIBLE, 24 * 9)],
        "기록 없음": [],
    })
    summary = summarize_statuses(statuses.values())
    assert summary == {
        "songs": 5, "checked_in_window": 3, "recent": 3, "retry": 3,
        BLOCKED: 1, COVER_ONLY: 1, VISIBLE: 2, UNCHECKED: 1,
    }


# --- 검사 한 회차 -----------------------------------------------------------

class FakeRun:
    """API·DB·크롤링을 가짜로 바꾼 회차. 기록된 결과와 검색한 검색어를 모은다."""

    def __init__(self, songs, checks=(), api=None, page_hits=(), requests=()):
        self.songs = songs
        self.checks = list(checks)
        self.api = api or (lambda query: [])
        self.page_hits = page_hits if isinstance(page_hits, Exception) else set(page_hits)
        self.requests = list(requests)
        self.recorded = []
        self.queries = []
        self.page_queries = []
        self.run_started = set()
        self.cleared = None

    def search(self, query, api_key):
        self.queries.append(query)
        result = self.api(query)
        if isinstance(result, Exception):
            raise result
        return result

    def page(self, query):
        """웹 검색 결과 페이지. page_hits 에 든 검색어(기본 또는 'cover' 붙인 것)면 그 곡의 영상이 보인다."""
        self.page_queries.append(query)
        if isinstance(self.page_hits, Exception):
            raise self.page_hits
        videos = {}
        for song in self.songs:
            videos[song["query"]] = videos[f"{song['query']} cover"] = song["video_id"]
        return [videos[query]] if query in self.page_hits else []

    def record(self, status, result, fallback_query=None, run_started_at=None):
        self.recorded.append((status.query, result, fallback_query))
        self.run_started.add(run_started_at)
        return True

    def clear(self, queries, before):
        self.cleared = (list(queries), before)

    def run(self):
        with patch.object(tasks, "fetch_search_songs", return_value=self.songs), \
             patch.object(tasks, "fetch_search_checks", return_value=self.checks), \
             patch.object(tasks, "fetch_search_requests", return_value=self.requests), \
             patch.object(tasks, "clear_applied_requests", side_effect=self.clear), \
             patch.object(tasks, "utc_now", return_value=NOW), \
             patch.object(tasks, "record_check", side_effect=self.record), \
             patch.object(tasks, "prune_old_checks"), \
             patch.object(tasks, "search_page_video_ids", side_effect=self.page), \
             patch.object(tasks, "SEARCH_API_KEY", ["key"]), \
             patch.object(tasks.time, "sleep"), \
             patch.object(tasks, "_youtube_video_ids_for_query", side_effect=self.search):
            return tasks.run_search_checks()


def test_one_run_never_exceeds_its_call_budget_and_keeps_a_cover_call_per_failure():
    run = FakeRun([_song(f"곡 {i:03d}") for i in range(200)])  # 전부 못 찾는다
    outcome = run.run()
    assert len(run.queries) <= tasks.SEARCH_CALLS_PER_RUN
    basic = [q for q in run.queries if not q.endswith(" cover")]
    cover = [q for q in run.queries if q.endswith(" cover")]
    assert cover == [f"{q} cover" for q in basic]  # 못 찾은 곡마다 cover 검색이 한 번씩
    assert {result for _, result, _ in run.recorded} == {BLOCKED}
    assert outcome["error"] == ""


def test_each_song_gets_one_of_three_results():
    run = FakeRun(
        [_song("보임"), _song("cover로만"), _song("웹에서 보임"), _song("웹 cover로만"), _song("막힘")],
        api=lambda query: {
            "보임": ["v-보임"],
            "cover로만 cover": ["v-cover로만"],
            "웹에서 보임 cover": ["v-웹에서 보임"],
        }.get(query, []),
        page_hits={"웹에서 보임", "웹 cover로만 cover"},
    )
    outcome = run.run()
    assert sorted(run.recorded) == sorted([
        ("보임", VISIBLE, None),
        ("cover로만", COVER_ONLY, "cover로만 cover"),
        # API 에 없어도 기본 검색어로 웹 검색 결과 페이지에 있으면 정상이다. cover 로 찾힐 곡이어도 마찬가지다.
        ("웹에서 보임", VISIBLE, None),
        ("웹 cover로만", COVER_ONLY, "웹 cover로만 cover"),  # cover 검색어로 웹에서만 보여도 cover로만
        ("막힘", BLOCKED, None),
    ])
    # 기본 검색어로 웹에서 찾은 곡은 cover API 를 쓰지 않는다.
    assert "웹에서 보임 cover" not in run.queries
    # 웹 검색은 API 에서 못 찾은 검색어만 보고, 기본 검색어를 cover 보다 먼저 본다.
    assert sorted(run.page_queries) == sorted(["cover로만", "웹에서 보임", "웹 cover로만", "막힘", "웹 cover로만 cover", "막힘 cover"])
    for query in ("cover로만", "웹 cover로만", "막힘"):
        assert run.page_queries.index(query) < run.page_queries.index("웹 cover로만 cover")
    assert "보임" not in run.page_queries and "cover로만 cover" not in run.page_queries
    stats = outcome["stats"]
    assert (stats["crawl_found"], stats["cover_found"], stats["cover_crawl_found"]) == (1, 1, 1)


def test_cover_is_checked_on_the_search_page_when_the_api_is_out():
    """API 가 회차 중간에 멈추면 cover API 검색을 못 한 곡도 cover 검색어로 웹 검색 결과 페이지는 본다."""
    calls = iter([[], requests.ConnectionError("끊김")])
    run = FakeRun([_song("a"), _song("b")], api=lambda query: next(calls), page_hits={"a cover"})
    outcome = run.run()
    assert run.queries == ["a", "b"]  # b 의 기본 검색에서 끊겨 a 의 cover API 검색은 못 한다
    assert run.page_queries == ["a", "a cover"]  # b 는 검사하지 않은 곡으로 남아 다음 회차에 온다
    assert run.recorded == [("a", COVER_ONLY, "a cover")]
    assert outcome["error"]


def test_a_blocked_search_page_stops_crawling_for_the_rest_of_the_run():
    run = FakeRun([_song("a"), _song("b")], page_hits=tasks.SearchPageBlocked())
    run.run()
    assert run.page_queries == ["a"]  # 막힌 뒤로는 기본·cover 검색어 모두 웹 검색을 하지 않는다
    assert sorted(run.queries) == sorted(["a", "a cover", "b", "b cover"])
    assert {result for _, result, _ in run.recorded} == {BLOCKED}


def test_an_api_error_keeps_what_was_already_checked():
    """예전에는 일시적 연결 오류 한 번으로 그 회차 결과를 통째로 버렸다."""
    calls = iter([["v-a"], [], requests.ConnectionError("끊김")])
    run = FakeRun([_song("a"), _song("b"), _song("c")], api=lambda query: next(calls))
    outcome = run.run()
    assert outcome["error"]
    # a 는 이미 정상으로 기록됐고, b 는 cover 검색 없이 웹 검색까지 보고 막힘으로 기록된다. c 는 다음 회차에 먼저 온다.
    assert run.recorded == [("a", VISIBLE, None), ("b", BLOCKED, None)]


def test_run_checks_the_sweep_share_first_then_recent_failures():
    songs = [_song("오래 정상"), _song("막힘")]
    checks = [_check("오래 정상", VISIBLE, _ago(days=9)), _check("막힘", BLOCKED, _ago(hours=8))]
    run = FakeRun(songs, checks, api=lambda query: ["v-오래 정상"] if query == "오래 정상" else [])
    outcome = run.run()
    assert run.queries == ["오래 정상", "막힘", "막힘 cover"]
    stats = outcome["stats"]
    assert (stats["retry_total"], stats["retry_checked"], stats["sweep_checked"]) == (1, 1, 1)


def test_run_that_cannot_read_the_song_list_is_reported_as_an_error():
    """DB 가 끊기면 목록 읽기가 빈 목록을 준다. '검사 0곡 완료'로 넘기지 않는다."""
    run = FakeRun([])
    outcome = run.run()
    assert outcome["error"] and run.queries == [] and run.recorded == []


def test_run_without_an_api_key_records_nothing():
    with patch.object(tasks, "SEARCH_API_KEY", []), patch.object(tasks, "record_check") as record:
        outcome = tasks.run_search_checks()
    assert outcome["error"] and not record.called


# --- 다음 회차: 최소·최대 목록과 관리자 조정 ------------------------------------------

def test_run_reach_gives_the_minimum_and_maximum_songs_per_run():
    """앞 곡이 모두 못 찾히면 cover 검색까지 2회씩이라 15곡, 모두 찾히면 29곡(30번째는 cover 몫으로 남긴다)."""
    assert history.run_reach(30) == (15, 29)
    assert history.run_reach(40) == (20, 39)


def test_run_reach_matches_what_a_run_actually_checks():
    every_fails = FakeRun([_song(f"곡 {i:03d}") for i in range(100)])
    every_fails.run()
    every_found = FakeRun([_song(f"곡 {i:03d}") for i in range(100)], api=lambda q: [f"v-{q}"])
    every_found.run()
    basic = lambda run: [q for q in run.queries if not q.endswith(" cover")]  # noqa: E731
    assert (len(basic(every_fails)), len(basic(every_found))) == history.run_reach(tasks.SEARCH_CALLS_PER_RUN)


def test_admin_first_requests_go_to_the_front_and_skips_drop_out():
    statuses = _statuses({
        "막힘": [(BLOCKED, 8)],
        "정상1": [(VISIBLE, 24 * 9)],
        "정상2": [(VISIBLE, 24 * 8)],
        "새 곡": [],
    })
    order = history.search_order(statuses.values(), 30, first=["정상2", "없는 곡"], skip={"막힘"})
    assert [(s.query, reason) for s, reason in order] == [
        ("정상2", history.REASON_FIRST),   # 관리자 요청이 맨 앞(목록에 없는 검색어는 무시)
        ("새 곡", history.REASON_SWEEP),
        ("정상1", history.REASON_SWEEP),
    ]


def test_split_requests_keeps_the_order_they_were_made():
    rows = [
        {"query": "b", "action": "first", "requested_at": NOW - timedelta(minutes=1)},
        {"query": "a", "action": "first", "requested_at": NOW - timedelta(minutes=5)},
        {"query": "c", "action": "skip", "requested_at": NOW},
    ]
    assert history.split_requests(rows) == (["a", "b"], {"c"})


def test_last_run_groups_records_by_run_start():
    run_9 = NOW - timedelta(hours=2)
    run_1 = NOW - timedelta(hours=10)
    checks = [
        {**_check("a", BLOCKED, run_1 + timedelta(minutes=1)), "run_started_at": run_1},
        {**_check("a", VISIBLE, run_9 + timedelta(minutes=1)), "run_started_at": run_9},
        {**_check("b", COVER_ONLY, run_9 + timedelta(minutes=2), fallback_query="b cover"), "run_started_at": run_9},
        {**_check("old", BLOCKED, run_9 + timedelta(minutes=3), video_id="옛 영상"), "run_started_at": run_9},
    ]
    statuses = build_statuses([_song("a"), _song("b"), _song("old")], checks, NOW)
    assert history.last_run(checks, statuses) == {"started_at": run_9, "songs": [("a", VISIBLE), ("b", COVER_ONLY)]}
    assert history.last_run([], statuses) is None


def test_a_run_tags_its_records_and_clears_only_the_requests_it_used():
    requests = [
        {"query": "요청 곡", "action": "first", "requested_at": NOW - timedelta(hours=1)},
        {"query": "뺄 곡", "action": "skip", "requested_at": NOW - timedelta(hours=1)},
    ]
    checks = [_check("뺄 곡", BLOCKED, _ago(hours=8))]
    run = FakeRun([_song("요청 곡"), _song("뺄 곡")], checks, api=lambda q: [f"v-{q}"], requests=requests)
    outcome = run.run()
    assert run.queries[0] == "요청 곡" and "뺄 곡" not in run.queries
    assert run.run_started == {NOW}  # 이 회차의 기록은 모두 회차 시작 시각으로 묶인다
    assert run.cleared == (["요청 곡", "뺄 곡"], NOW)
    assert outcome["stats"]["requested_checked"] == 1
    assert "관리자 요청 1곡" in tasks.summarize_search_run(outcome["stats"])


def test_plan_next_run_is_computed_for_the_next_run_start():
    """다음 회차 순서는 예상이 아니라 그 회차가 시작할 시각 기준으로 실제 회차와 똑같이 계산한다."""
    checks = [_check(f"곡{i:02d}", BLOCKED, _ago(hours=8 + i)) for i in range(20)]
    state = {
        "songs": [_song(f"곡{i:02d}") for i in range(20)] + [_song("새 곡")],
        "checks": checks,
        "requests": [{"query": "곡05", "action": "first", "requested_at": NOW}],
        "now": NOW,
    }
    plan = tasks.plan_next_run(state)
    assert plan["starts_at"] == datetime(2026, 11, 7, 8, 0)  # NOW(03:00 UTC) 다음 8시간 경계
    assert plan["sure"] == 15 and len(plan["order"]) == 21
    assert [s.query for s, _ in plan["order"][:3]] == ["곡05", "새 곡", "곡19"]


# --- 검색 일정: 글자로 적지 않고 설정값에서 계산한다 ------------------------------

def test_schedule_is_computed_from_the_interval(monkeypatch):
    assert tasks.search_run_hours_kst() == [1, 9, 17]  # 지금 설정: 8시간(UTC 0·8·16시)
    assert tasks.next_search_run_epoch(8 * 3600 * 10 + 5) == 8 * 3600 * 11
    monkeypatch.setattr(tasks, "SEARCH_API_INTERVAL", 6 * 3600)
    assert tasks.search_run_hours_kst() == [3, 9, 15, 21]
    assert tasks.next_search_run_epoch(6 * 3600 * 10) == 6 * 3600 * 11


def test_admin_schedule_text_follows_the_settings(monkeypatch):
    from stelline.admin import server_logs

    assert "한국 시간 01·09·17시(하루 3회)" in server_logs.search_schedule_text()
    assert f"API {tasks.SEARCH_CALLS_PER_RUN}회" in server_logs.search_schedule_text()
    monkeypatch.setattr(tasks, "SEARCH_API_INTERVAL", 6 * 3600)
    assert "한국 시간 03·09·15·21시(하루 4회)" in server_logs.search_schedule_text()


@pytest.mark.parametrize(
    "videos,expected",
    [(["x", "v-곡", "y", "z"], True), (["x", "y", "z", "v-곡"], False)],
)
def test_search_page_crawl_only_trusts_the_top_three(videos, expected):
    data = {"contents": {"twoColumnSearchResultsRenderer": {"primaryContents": {"sectionListRenderer": {
        "contents": [{"itemSectionRenderer": {"contents": [{"videoRenderer": {"videoId": v}} for v in videos]}}],
    }}}}}

    class Response:
        text = "var ytInitialData = " + json.dumps(data) + ";"

        def raise_for_status(self):
            return None

    with patch.object(tasks.SESSION, "get", return_value=Response()), patch.object(tasks.time, "sleep"):
        video_ids = tasks.search_page_video_ids("곡")
    assert ("v-곡" in video_ids) is expected


def test_search_page_without_results_json_is_treated_as_blocked(caplog):
    # 2026-11-14 09시 회차: 결과 JSON 이 없는 페이지가 오자 막힌 7곡 모두에서 같은 오류가 났다.
    class Response:
        status_code = 200
        url = "https://www.youtube.com/results?search_query=x"
        text = "<html><head><title>YouTube</title></head><body>다른 페이지</body></html>"

        def raise_for_status(self):
            return None

    with patch.object(tasks.SESSION, "get", return_value=Response()), \
         patch.object(tasks.time, "sleep"), caplog.at_level("ERROR"), \
         pytest.raises(tasks.SearchPageBlocked):
        tasks.search_page_video_ids("곡1")

    failures = [r.getMessage() for r in caplog.records if "크롤링 데이터 파싱 실패" in r.getMessage()]
    assert failures == [
        "크롤링 데이터 파싱 실패: 곡1 · HTTP 200 · www.youtube.com/results · 67자 · 제목 'YouTube' · ytInitialData 없음"
    ]


def test_search_page_description_shows_an_unexpected_initial_data_shape():
    class Response:
        status_code = 200
        url = "https://consent.youtube.com/m?continue=x"
        text = "var ytInitialData = '\\x7b\\x22responseContext';"

    described = tasks.describe_search_page(Response())
    assert "consent.youtube.com/m" in described
    assert "제목 없음" in described
    assert "ytInitialData 뒤 \" = '\\\\x7b" in described  # 문자열로 감싼 JSON 인지 보인다


def test_search_page_connection_failure_is_treated_as_blocked():
    with patch.object(tasks.SESSION, "get", side_effect=requests.ConnectionError("막힘")), \
         patch.object(tasks.time, "sleep"), pytest.raises(tasks.SearchPageBlocked):
        tasks.search_page_video_ids("곡")
