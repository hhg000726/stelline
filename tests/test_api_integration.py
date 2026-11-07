"""실제 MySQL을 상대로 한 기능 API 통합 테스트."""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from stelline.apis import reports
from tests.conftest import requires_db

pytestmark = requires_db


def _insert(db, sql, params):
    with db.cursor() as cursor:
        cursor.execute(sql, params)
    db.commit()


def _scalar(db, sql, params=()):
    with db.cursor() as cursor:
        cursor.execute(sql, params)
        row = cursor.fetchone()
    return next(iter(row.values())) if row else None


# --- main 화면 데이터 -------------------------------------------------

def test_record_main_increments_counter(client, db, clean_db):
    assert _scalar(db, "SELECT copy_count FROM record_main") == 0
    resp = client.get("/api/main/record")
    assert resp.status_code == 204
    assert _scalar(db, "SELECT copy_count FROM record_main") == 1


def test_events_and_twits_listing(client, db, clean_db):
    _insert(
        db,
        "INSERT INTO events (title, link, expires_at) VALUES (%s, %s, %s)",
        ("콘서트", "https://example.com", datetime.now() + timedelta(days=3)),
    )
    _insert(
        db,
        "INSERT INTO twits (title, tags, keywords) VALUES (%s, %s, %s)",
        ("공지", "tag1,tag2", "kw"),
    )

    events = client.get("/api/main/events").get_json()
    twits = client.get("/api/main/twits").get_json()

    assert [e["title"] for e in events] == ["콘서트"]
    assert [t["title"] for t in twits] == ["공지"]


# --- search 기능 ----------------------------------------------------
# 노출 판정은 검사 기록(search_checks)에서만 나온다. 옛 열(risk·fallback_query)과
# 옛 표(songs_data·recent_data)에 값이 남아 있어도 화면에 섞이면 안 된다.

def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _song(db, query, video_id, **legacy):
    columns = ["query", "video_id", *legacy]
    _insert(
        db,
        f"INSERT INTO song_infos ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})",
        (query, video_id, *legacy.values()),
    )


def _check(db, query, video_id, result, hours_ago, fallback_query=None):
    _insert(
        db,
        "INSERT INTO search_checks (query, video_id, result, fallback_query, checked_at) VALUES (%s, %s, %s, %s, %s)",
        (query, video_id, result, fallback_query, _utc_now() - timedelta(hours=hours_ago)),
    )


def _seed_search_history(db):
    _song(db, "곡 A", "vidA", risk=0)                                   # 두 회차 전 마지막 검사에서 막힘
    _check(db, "곡 A", "vidA", "visible", 40)
    _check(db, "곡 A", "vidA", "blocked", 16)
    _song(db, "곡 B", "vidB", risk=28)                                  # 막혔다가 지금은 보임
    _check(db, "곡 B", "vidB", "blocked", 48)
    _check(db, "곡 B", "vidB", "visible", 8)
    _song(db, "곡 C", "vidC", risk=0, fallback_query="옛 값")           # 지금 cover 로만 찾힘
    _check(db, "곡 C", "vidC", "cover_only", 8, "곡 C cover")
    _song(db, "곡 D", "vidD", risk=28, fallback_query="옛 값")          # 기록 없음(옛 열은 무시)
    _song(db, "곡 E", "vidE")                                          # 9일 전에 막혔고 그 뒤 정상
    _check(db, "곡 E", "vidE", "blocked", 24 * 9)
    _check(db, "곡 E", "vidE", "visible", 24 * 5)
    # 옛 표에 남은 값은 판정에 쓰지 않는다.
    _insert(db, "INSERT INTO songs_data (video_id, query, searched_time) VALUES (%s, %s, %s)", ("vidE", "곡 E", time.time()))


def test_search_status_judges_each_song_by_its_own_records(client, db, clean_db):
    _seed_search_history(db)
    payload = client.get("/api/search/status").get_json()

    songs = {song["query"]: song for song in payload["songs"]}
    # state: 마지막 검사 결과('지금 막힘'·'cover 검색으로 발견' 탭), recent: 7일 안에 검색이 안 된 적('최근 7일' 탭)
    assert {query: (song["state"], song["recent"]) for query, song in songs.items()} == {
        "곡 A": ("blocked", True),
        "곡 B": ("visible", True),
        "곡 C": ("cover_only", True),
        "곡 D": ("unchecked", False),
        "곡 E": ("visible", False),
    }
    assert songs["곡 E"]["retry"] is True  # 9일 전 막힘: 화면의 7일은 지났지만 재시도(14일)는 한다
    assert songs["곡 A"]["week"]["checks"] == 2 and songs["곡 A"]["week"]["blocked"] == 1
    assert [r["result"] for r in songs["곡 A"]["week"]["results"]] == ["visible", "blocked"]
    assert songs["곡 C"]["fallback_query"] == "곡 C cover"
    assert songs["곡 D"]["fallback_query"] is None and songs["곡 D"]["checked_at"] is None
    assert "risk" not in songs["곡 A"]  # 판정에 쓰지 않던 위험도는 내보내지 않는다
    assert songs["곡 E"]["week"]["checks"] == 1  # 9일 전 기록은 7일 밖이다
    assert payload["summary"]["checked_in_window"] == 4
    assert (payload["summary"]["blocked"], payload["summary"]["recent"], payload["summary"]["cover_only"]) == (1, 3, 1)
    assert payload["window_days"] == 7
    # 화면의 '다음 검색' 시각과 간격은 서버 설정에서 온다.
    schedule = payload["schedule"]
    assert (schedule["interval_hours"], schedule["run_hours_kst"]) == (8, [1, 9, 17])
    # 다음 회차: 그 회차가 시작할 시각과, 최소 목록(sure)·최대 목록이 정해진 순서.
    next_run = payload["next_run"]
    assert next_run["at"] % (8 * 3600) == 0 and next_run["at"] > payload["generated_at"]
    assert next_run["sure"] == len(songs) == len(next_run["songs"])  # 곡이 15곡보다 적으면 모두 확정
    # 순회 몫(검사 전인 곡 D) 다음에 재시도 대상을 오래 기다린 순서로: E(5일 전) → A(16시간 전) → B·C(8시간 전)
    assert [s["query"] for s in next_run["songs"]] == ["곡 D", "곡 E", "곡 A", "곡 B", "곡 C"]
    assert [s["reason"] for s in next_run["songs"][:2]] == ["sweep", "retry"]
    # 회차 시작 시각이 없는 기록(016 전)만 있으면 지난 회차는 없다.
    assert payload["last_run"] is None
    assert payload["last_checked_at"] == max(s["checked_at"] for s in songs.values() if s["checked_at"])


def test_not_searched_keeps_its_shape_for_outside_readers(client, db, clean_db):
    _seed_search_history(db)
    payload = client.get("/api/search/not_searched").get_json()

    assert set(payload) == {"all_songs", "searched_time", "recent", "cover_matches"}
    assert payload["all_songs"] == [{"query": "곡 A", "video_id": "vidA"}]
    # 최근 7일 안에 '막힘'이 있었던 곡. searched_time 은 마지막으로 막힌 시각(epoch 초).
    assert [r["query"] for r in payload["recent"]] == ["곡 A", "곡 B"]
    blocked_b = (_utc_now() - timedelta(hours=48)).replace(tzinfo=timezone.utc).timestamp()
    assert abs(payload["recent"][1]["searched_time"] - blocked_b) < 5
    assert payload["cover_matches"] == [{"query": "곡 C", "video_id": "vidC", "fallback_query": "곡 C cover"}]
    assert payload["searched_time"] > 0


def test_song_list_keeps_old_keys_except_risk(client, db, clean_db):
    _seed_search_history(db)
    data = {song["query"]: song for song in client.get("/api/search/songs").get_json()}

    assert list(data) == ["곡 A", "곡 B", "곡 C", "곡 D", "곡 E"]  # 가나다순
    # 예전 키 가운데 risk 만 뺐다. 판정에 쓰지 않던 값이고, 옛 열(곡 D 의 28)도 내보내지 않는다.
    assert set(data["곡 A"]) == {"video_id", "query", "fallback_query", "state", "checked_at"}
    assert data["곡 D"]["fallback_query"] is None  # 옛 열의 값을 쓰지 않는다


def test_last_run_lists_what_the_latest_run_checked(client, db, clean_db):
    _song(db, "곡 A", "vidA")
    _song(db, "곡 B", "vidB")
    started = _utc_now() - timedelta(hours=2)
    rows = [
        ("곡 A", "vidA", "visible", started - timedelta(hours=8), started - timedelta(hours=8)),  # 그 전 회차
        ("곡 A", "vidA", "blocked", started + timedelta(minutes=1), started),
        ("곡 B", "vidB", "cover_only", started + timedelta(minutes=2), started),
    ]
    with db.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO search_checks (query, video_id, result, checked_at, run_started_at) VALUES (%s, %s, %s, %s, %s)",
            rows,
        )
    db.commit()
    last_run = client.get("/api/search/status").get_json()["last_run"]
    assert last_run == {
        "started_at": started.replace(tzinfo=timezone.utc).timestamp(),
        "songs": [{"query": "곡 A", "result": "blocked"}, {"query": "곡 B", "result": "cover_only"}],
    }


def test_admin_adjustments_change_the_next_run_at_once(admin_client, db, clean_db):
    """관리자가 조정하면 저장하자마자 다음 회차 순서가 다시 계산된다(공개 API 도 같은 순서)."""
    _seed_search_history(db)

    def next_order():
        return [s["query"] for s in admin_client.get("/api/search/status").get_json()["next_run"]["songs"]]

    def adjust(action, query):
        return admin_client.post("/admin/search/next", data={"csrf_token": admin_client.csrf, "action": action, "query": query})

    assert next_order()[0] == "곡 D"
    assert adjust("first", "곡 C").status_code == 302
    assert next_order()[:2] == ["곡 C", "곡 D"]
    adjust("skip", "곡 D")
    assert "곡 D" not in next_order()
    adjust("cancel", "곡 D")
    assert "곡 D" in next_order()
    adjust("first", "목록에 없는 곡")
    assert _scalar(db, "SELECT COUNT(*) FROM search_requests WHERE query = %s", ("목록에 없는 곡",)) == 0
    html = admin_client.get("/admin/").get_data(as_text=True)
    assert "data-search-next" in html and "최소 목록" in html and "관리자 요청" in html


def test_search_status_is_empty_but_well_formed_without_records(client, db, clean_db):
    payload = client.get("/api/search/status").get_json()
    assert payload["songs"] == [] and payload["last_checked_at"] is None
    assert client.get("/api/search/not_searched").get_json()["searched_time"] == 0


def test_record_search_increments_copy_count(client, db, clean_db):
    resp = client.get("/api/search/record")
    assert resp.status_code == 204
    assert _scalar(db, "SELECT copy_count FROM record_search") == 1


def test_song_report_is_persisted(client, db, clean_db):
    with patch.object(reports, "verify_turnstile", return_value=True):
        resp = client.post(
            "/api/search/reports", json={"content": "검색 안 되는 곡입니다", "captcha_token": "ok"}
        )
    assert resp.status_code == 201
    assert _scalar(db, "SELECT content FROM song_reports") == "검색 안 되는 곡입니다"


# --- congratulation 기능 ------------------------------------------

def test_congratulations_only_returns_recent(client, db, clean_db):
    fresh = datetime.now() - timedelta(hours=2)
    stale = datetime.now() - timedelta(days=3)
    _insert(
        db,
        "INSERT INTO song_counts (video_id, title, count, counted_time) VALUES (%s, %s, %s, %s)",
        ("fresh", "최근 달성", 1_000_000, fresh),
    )
    _insert(
        db,
        "INSERT INTO song_counts (video_id, title, count, counted_time) VALUES (%s, %s, %s, %s)",
        ("stale", "오래된 달성", 2_000_000, stale),
    )
    data = client.get("/api/congratulation/congratulations").get_json()
    assert [row["video_id"] for row in data] == ["fresh"]


def test_view_report_is_persisted(client, db, clean_db):
    with patch.object(reports, "verify_turnstile", return_value=True):
        resp = client.post(
            "/api/congratulation/reports",
            json={"content": "조회수 알림 누락", "captcha_token": "ok"},
        )
    assert resp.status_code == 201
    assert _scalar(db, "SELECT content FROM view_reports") == "조회수 알림 누락"


def test_fcm_token_register_is_idempotent(client, db, clean_db):
    first = client.post("/api/congratulation/register", json={"token": "tok-1"})
    second = client.post("/api/congratulation/register", json={"token": "tok-1"})
    assert first.status_code == 200 and second.status_code == 200
    assert _scalar(db, "SELECT COUNT(*) FROM fcm_tokens WHERE token = 'tok-1'") == 1


def test_fcm_token_check_and_unregister(client, db, clean_db):
    client.post("/api/congratulation/register", json={"token": "tok-2"})

    assert client.post("/api/congratulation/check-token", json={"token": "tok-2"}).get_json() == {
        "valid": True
    }

    unreg = client.post("/api/congratulation/unregister", json={"token": "tok-2"})
    assert unreg.status_code == 200
    assert _scalar(db, "SELECT COUNT(*) FROM fcm_tokens WHERE token = 'tok-2'") == 0

    assert client.post("/api/congratulation/check-token", json={"token": "tok-2"}).get_json() == {
        "valid": False
    }


def test_fcm_register_requires_token(client, clean_db):
    resp = client.post("/api/congratulation/register", json={})
    assert resp.status_code == 400


# --- offline 기능 -------------------------------------------------

def test_offline_events_backfill_coordinates(client, db, clean_db):
    _insert(
        db,
        "INSERT INTO offline (name, address, latitude, longitude) VALUES (%s, %s, %s, %s)",
        ("팝업스토어", "서울시 강남구", 0, 0),
    )
    with patch(
        "stelline.apis.offline.service.geocode_location", return_value=(37.5, 127.05)
    ) as geo:
        resp = client.get("/api/offline/offline_api")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body[0]["latitude"] == 37.5 and body[0]["longitude"] == 127.05
    geo.assert_called_once()
    # DB에도 좌표가 저장되어야 한다.
    assert _scalar(db, "SELECT latitude FROM offline WHERE name = '팝업스토어'") == 37.5


def test_offline_events_skip_geocode_when_coordinates_present(client, db, clean_db):
    _insert(
        db,
        "INSERT INTO offline (name, address, latitude, longitude) VALUES (%s, %s, %s, %s)",
        ("행사장", "서울시 종로구", 37.57, 126.98),
    )
    with patch("stelline.apis.offline.service.geocode_location") as geo:
        resp = client.get("/api/offline/offline_api")
    assert resp.status_code == 200
    geo.assert_not_called()
