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
