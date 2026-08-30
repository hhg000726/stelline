"""관리자 화면·CRUD 통합 테스트 (실제 MySQL)."""

from datetime import datetime, timedelta

from tests.conftest import requires_db

pytestmark = requires_db


def _scalar(db, sql, params=()):
    with db.cursor() as cursor:
        cursor.execute(sql, params)
        row = cursor.fetchone()
    return next(iter(row.values())) if row else None


def test_admin_index_renders_for_logged_in_user(admin_client, clean_db):
    resp = admin_client.get("/admin/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "이벤트·펀딩" in html
    assert "Bugs 순위 대상" in html


def test_admin_index_shows_existing_rows(admin_client, db, clean_db):
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO events (title, link, expires_at) VALUES (%s, %s, %s)",
            ("관리자에게 보이는 이벤트", "https://example.com", datetime.now() + timedelta(days=1)),
        )
    db.commit()
    html = admin_client.get("/admin/").get_data(as_text=True)
    assert "관리자에게 보이는 이벤트" in html


def test_admin_add_row_inserts(admin_client, db, clean_db):
    resp = admin_client.post(
        "/admin/data/events",
        data={
            "csrf_token": admin_client.csrf,
            "title": "새 이벤트",
            "link": "https://example.com/new",
            "expires_at": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert _scalar(db, "SELECT link FROM events WHERE title = '새 이벤트'") == "https://example.com/new"


def test_admin_add_row_rejects_bad_csrf(admin_client, db, clean_db):
    resp = admin_client.post(
        "/admin/data/events",
        data={"csrf_token": "wrong", "title": "차단될 이벤트", "link": "x"},
    )
    assert resp.status_code == 400
    assert _scalar(db, "SELECT COUNT(*) FROM events") == 0


def test_admin_add_row_unknown_table_404(admin_client, clean_db):
    resp = admin_client.post(
        "/admin/data/secret_table", data={"csrf_token": admin_client.csrf, "x": "y"}
    )
    assert resp.status_code == 404


def test_admin_delete_row(admin_client, db, clean_db):
    with db.cursor() as cursor:
        cursor.execute("INSERT INTO song_reports (content) VALUES (%s)", ("삭제 대상 제보",))
        cursor.execute("SELECT id FROM song_reports WHERE content = '삭제 대상 제보'")
        row_id = cursor.fetchone()["id"]
    db.commit()

    from stelline.admin.routes import serialize_row

    token = serialize_row({"id": row_id})
    resp = admin_client.post(
        "/admin/data/song_reports/delete",
        data={"csrf_token": admin_client.csrf, "row_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert _scalar(db, "SELECT COUNT(*) FROM song_reports") == 0


def test_admin_endpoints_require_login(client, clean_db):
    # 세션 없는 client
    for method, path in [
        ("get", "/admin/"),
        ("post", "/admin/data/events"),
        ("post", "/admin/data/events/delete"),
    ]:
        resp = getattr(client, method)(path, follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]


def test_admin_update_row_edits_existing_content(admin_client, db, clean_db):
    """수정 기능은 노래방 전용이 아니라 모든 콘텐츠 테이블에서 동작한다."""
    with db.cursor() as cursor:
        cursor.execute("INSERT INTO events (title, link) VALUES (%s, %s)", ("수정 전 이벤트", "https://example.com/old"))
        cursor.execute("SELECT * FROM events WHERE title = '수정 전 이벤트'")
        row = cursor.fetchone()
    db.commit()

    from stelline.admin.routes import serialize_row

    resp = admin_client.post(
        "/admin/data/events/update",
        data={
            "csrf_token": admin_client.csrf,
            "row_token": serialize_row(row),
            "title": "수정 후 이벤트",
            "link": "https://example.com/new",
            "expires_at": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert _scalar(db, "SELECT COUNT(*) FROM events") == 1
    assert _scalar(db, "SELECT link FROM events WHERE title = '수정 후 이벤트'") == "https://example.com/new"


def test_admin_update_row_reports_missing_target(admin_client, db, clean_db):
    from stelline.admin.routes import serialize_row

    token = serialize_row({"title": "없는 이벤트", "link": "x", "expires_at": None})
    resp = admin_client.post(
        "/admin/data/events/update",
        data={"csrf_token": admin_client.csrf, "row_token": token, "title": "새 제목", "link": "y"},
        follow_redirects=True,
    )
    assert "수정할 항목을 찾지 못했습니다" in resp.get_data(as_text=True)
    assert _scalar(db, "SELECT COUNT(*) FROM events") == 0
