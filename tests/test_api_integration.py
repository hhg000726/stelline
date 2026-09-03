"""실제 MySQL을 상대로 한 기능 API 통합 테스트."""

import time
from datetime import datetime, timedelta
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

def test_get_song_infos(client, db, clean_db):
    _insert(
        db,
        "INSERT INTO song_infos (video_id, query, risk) VALUES (%s, %s, %s)",
        ("vid123", "테스트 곡", 5),
    )
    data = client.get("/api/search/songs").get_json()
    assert data == [{"video_id": "vid123", "query": "테스트 곡", "risk": 5}]


def test_not_searched_returns_songs_and_recent(client, db, clean_db):
    now = time.time()
    _insert(
        db,
        "INSERT INTO songs_data (video_id, query, searched_time) VALUES (%s, %s, %s)",
        ("vidA", "곡 A", now),
    )
    _insert(
        db,
        "INSERT INTO recent_data (video_id, query, searched_time) VALUES (%s, %s, %s)",
        ("vidB", "곡 B", now),
    )
    payload = client.get("/api/search/not_searched").get_json()
    assert {"query": "곡 A", "video_id": "vidA"} in payload["all_songs"]
    assert any(r["video_id"] == "vidB" for r in payload["recent"])


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
