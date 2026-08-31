"""노래방 번호 기능 통합 테스트 (실제 MySQL)."""

from unittest.mock import patch

import pytest

from stelline.admin.routes import serialize_row
from stelline.apis import reports
from stelline.database import karaoke_release_dates as release_dates
from tests.conftest import requires_db

pytestmark = requires_db


def _insert_song(db, title, artist, **overrides):
    values = {
        "title": title, "artist": artist, "members": None, "section": "solo",
        "category": "cover", "tj": None, "ky": None, "note": None, "sort_order": 0,
    }
    values.update(overrides)
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO karaoke_songs (title, artist, members, section, category, tj, ky, note, sort_order)"
            " VALUES (%(title)s, %(artist)s, %(members)s, %(section)s, %(category)s, %(tj)s, %(ky)s, %(note)s, %(sort_order)s)",
            values,
        )
        cursor.execute("SELECT * FROM karaoke_songs WHERE title = %s AND artist = %s", (title, artist))
        return cursor.fetchone()


def _scalar(db, sql, params=()):
    with db.cursor() as cursor:
        cursor.execute(sql, params)
        row = cursor.fetchone()
    return next(iter(row.values())) if row else None


# ---------- 공개 API ----------

def test_songs_api_returns_empty_payload_without_data(client, clean_db):
    resp = client.get("/api/karaoke/songs")
    assert resp.status_code == 200
    assert resp.get_json() == {"songs": [], "members": [], "updatedAt": ""}


def test_songs_api_serializes_row(client, db, clean_db):
    _insert_song(db, "테스트곡", "아이리 칸나", members="아이리 칸나, 유즈하 리코", tj="12345", section="unit", category="original", note="메모")
    payload = client.get("/api/karaoke/songs").get_json()

    assert len(payload["songs"]) == 1
    song = payload["songs"][0]
    assert song["title"] == "테스트곡"
    assert song["members"] == ["아이리 칸나", "유즈하 리코"]
    assert song["tj"] == "12345"
    assert song["ky"] == ""  # 번호 없음은 빈 문자열로 내려간다
    assert song["section"] == "unit"
    assert song["category"] == "original"
    assert song["note"] == "메모"
    assert payload["updatedAt"]


def test_songs_api_orders_by_sort_order(client, db, clean_db):
    _insert_song(db, "세번째", "칸나", sort_order=30)
    _insert_song(db, "첫번째", "칸나", sort_order=10)
    _insert_song(db, "두번째", "칸나", sort_order=20)
    titles = [song["title"] for song in client.get("/api/karaoke/songs").get_json()["songs"]]
    assert titles == ["첫번째", "두번째", "세번째"]


def test_songs_api_uses_member_master_when_present(client, db, clean_db):
    _insert_song(db, "테스트곡", "칸나", members="아야츠노 유니")
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO karaoke_members (name, unit, former_units, graduated_at, display_order)"
            " VALUES ('아야츠노 유니', 'EVERYS', 'MYSTIC', NULL, 1)"
        )
    payload = client.get("/api/karaoke/songs").get_json()
    # 졸업 여부는 데이터 검증용이라 공개 API에 담지 않는다.
    assert payload["members"] == [{"name": "아야츠노 유니", "unit": "EVERYS", "formerUnits": ["MYSTIC"]}]


def test_songs_api_falls_back_to_members_written_on_songs(client, db, clean_db):
    """멤버 마스터를 아직 채우지 않아도 화면의 멤버 필터가 비지 않아야 한다."""
    _insert_song(db, "테스트곡", "유닛", members="유즈하 리코, 아이리 칸나")
    payload = client.get("/api/karaoke/songs").get_json()
    assert {member["name"] for member in payload["members"]} == {"유즈하 리코", "아이리 칸나"}
    assert all(member["unit"] == "" for member in payload["members"])


def test_songs_api_supports_conditional_request(client, db, clean_db):
    _insert_song(db, "테스트곡", "칸나")
    first = client.get("/api/karaoke/songs")
    assert first.headers.get("ETag")
    second = client.get("/api/karaoke/songs", headers={"If-None-Match": first.headers["ETag"]})
    assert second.status_code == 304


def test_record_copy_increases_counter(client, db, clean_db):
    assert client.post("/api/karaoke/record_copy").status_code == 200
    assert _scalar(db, "SELECT copy_count FROM record_karaoke") == 1


def test_report_is_stored(client, db, clean_db):
    with patch.object(reports, "verify_turnstile", return_value=True):
        resp = client.post("/api/karaoke/reports", json={"content": "용사 TJ 번호 정정", "captcha_token": "ok"})
    assert resp.status_code == 201
    assert _scalar(db, "SELECT content FROM karaoke_reports") == "용사 TJ 번호 정정"


def test_report_requires_captcha(client, db, clean_db):
    resp = client.post("/api/karaoke/reports", json={"content": "내용", "captcha_token": "bad"})
    assert resp.status_code == 400
    assert _scalar(db, "SELECT COUNT(*) FROM karaoke_reports") == 0


# ---------- 관리자 일괄 등록 ----------

def test_bulk_import_from_pasted_table(admin_client, db, clean_db):
    resp = admin_client.post(
        "/admin/karaoke/import",
        data={"csrf_token": admin_client.csrf, "source": "paste", "bulk_text": "곡A\t아이리 칸나\t111\t-\n곡B\t유즈하 리코\t-\t222"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    with db.cursor() as cursor:
        cursor.execute("SELECT title, tj, ky FROM karaoke_songs ORDER BY title")
        rows = cursor.fetchall()
    assert rows == [{"title": "곡A", "tj": "111", "ky": None}, {"title": "곡B", "tj": None, "ky": "222"}]


def test_bulk_import_updates_existing_song_instead_of_duplicating(admin_client, db, clean_db):
    _insert_song(db, "곡A", "아이리 칸나", tj="111")
    admin_client.post(
        "/admin/karaoke/import",
        data={"csrf_token": admin_client.csrf, "source": "paste", "bulk_text": "곡A\t아이리 칸나\t111\t999"},
    )
    assert _scalar(db, "SELECT COUNT(*) FROM karaoke_songs") == 1
    assert _scalar(db, "SELECT ky FROM karaoke_songs WHERE title = '곡A'") == "999"


def test_bulk_import_keeps_existing_ids_so_shared_links_survive(admin_client, db, clean_db):
    original = _insert_song(db, "곡A", "아이리 칸나", tj="111")
    admin_client.post(
        "/admin/karaoke/import",
        data={"csrf_token": admin_client.csrf, "source": "paste", "bulk_text": "곡A\t아이리 칸나\t111\t999"},
    )
    assert _scalar(db, "SELECT id FROM karaoke_songs WHERE title = '곡A'") == original["id"]


def test_bulk_import_with_replace_clears_previous_songs(admin_client, db, clean_db):
    _insert_song(db, "지워질 곡", "칸나")
    admin_client.post(
        "/admin/karaoke/import",
        data={"csrf_token": admin_client.csrf, "source": "paste", "replace": "on", "bulk_text": "남을 곡\t칸나\t1\t2"},
    )
    with db.cursor() as cursor:
        cursor.execute("SELECT title FROM karaoke_songs")
        assert [row["title"] for row in cursor.fetchall()] == ["남을 곡"]


def test_bulk_import_rejects_invalid_number(admin_client, db, clean_db):
    resp = admin_client.post(
        "/admin/karaoke/import",
        data={"csrf_token": admin_client.csrf, "source": "paste", "bulk_text": "곡A\t칸나\tABC\t1"},
        follow_redirects=True,
    )
    assert "숫자만 입력하세요" in resp.get_data(as_text=True)
    assert _scalar(db, "SELECT COUNT(*) FROM karaoke_songs") == 0


def test_bulk_import_requires_csrf(admin_client, db, clean_db):
    resp = admin_client.post("/admin/karaoke/import", data={"source": "paste", "bulk_text": "곡A\t칸나\t1\t2"})
    assert resp.status_code == 400
    assert _scalar(db, "SELECT COUNT(*) FROM karaoke_songs") == 0


def test_bulk_import_requires_login(client, db, clean_db):
    resp = client.post("/admin/karaoke/import", data={"source": "paste", "bulk_text": "곡A\t칸나\t1\t2"})
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
    assert _scalar(db, "SELECT COUNT(*) FROM karaoke_songs") == 0


def test_seed_file_import_loads_reference_list(admin_client, db, clean_db):
    resp = admin_client.post(
        "/admin/karaoke/import",
        data={"csrf_token": admin_client.csrf, "source": "seed"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert _scalar(db, "SELECT COUNT(*) FROM karaoke_songs") > 200
    # 멤버 마스터도 함께 채워져 공개 화면 필터가 바로 동작한다.
    assert _scalar(db, "SELECT COUNT(*) FROM karaoke_members") == 11


# ---------- 관리자 개별 편집 ----------

def test_admin_can_add_song_with_defaults_for_blank_fields(admin_client, db, clean_db):
    resp = admin_client.post(
        "/admin/data/karaoke_songs",
        data={"csrf_token": admin_client.csrf, "title": "새 곡", "artist": "칸나", "tj": "555", "ky": "", "section": "solo", "category": "cover"},
    )
    assert resp.status_code == 302
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM karaoke_songs WHERE title = '새 곡'")
        row = cursor.fetchone()
    assert row["tj"] == "555"
    assert row["ky"] is None
    assert row["sort_order"] == 0  # 빈 칸은 열 기본값을 쓴다


def test_admin_update_changes_only_submitted_row(admin_client, db, clean_db):
    target = _insert_song(db, "수정될 곡", "칸나", tj="111")
    other = _insert_song(db, "그대로 둘 곡", "칸나", tj="222")

    resp = admin_client.post(
        "/admin/data/karaoke_songs/update",
        data={
            "csrf_token": admin_client.csrf, "row_token": serialize_row(target),
            "title": "수정된 곡", "artist": "칸나", "tj": "999", "ky": "888",
            "section": "unit", "category": "original",
        },
    )
    assert resp.status_code == 302
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM karaoke_songs WHERE id = %s", (target["id"],))
        updated = cursor.fetchone()
        cursor.execute("SELECT * FROM karaoke_songs WHERE id = %s", (other["id"],))
        untouched = cursor.fetchone()
    assert (updated["title"], updated["tj"], updated["ky"], updated["section"]) == ("수정된 곡", "999", "888", "unit")
    assert (untouched["title"], untouched["tj"]) == ("그대로 둘 곡", "222")


def test_admin_update_clears_nullable_field_left_blank(admin_client, db, clean_db):
    target = _insert_song(db, "번호 지울 곡", "칸나", tj="111", ky="222")
    admin_client.post(
        "/admin/data/karaoke_songs/update",
        data={
            "csrf_token": admin_client.csrf, "row_token": serialize_row(target),
            "title": "번호 지울 곡", "artist": "칸나", "tj": "", "ky": "222",
            "section": "solo", "category": "cover",
        },
    )
    assert _scalar(db, "SELECT tj FROM karaoke_songs WHERE id = %s", (target["id"],)) is None


def test_admin_update_keeps_not_null_field_left_blank(admin_client, db, clean_db):
    """NOT NULL 열은 비워도 지울 수 없으므로 기존 값을 유지한다."""
    target = _insert_song(db, "구분 유지 곡", "칸나", section="unit", sort_order=7)
    admin_client.post(
        "/admin/data/karaoke_songs/update",
        data={
            "csrf_token": admin_client.csrf, "row_token": serialize_row(target),
            "title": "구분 유지 곡", "artist": "칸나", "section": "", "category": "", "sort_order": "",
        },
    )
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM karaoke_songs WHERE id = %s", (target["id"],))
        row = cursor.fetchone()
    assert (row["section"], row["category"], row["sort_order"]) == ("unit", "cover", 7)


def test_admin_update_rejects_forged_row_token(admin_client, db, clean_db):
    _insert_song(db, "보호되는 곡", "칸나", tj="111")
    resp = admin_client.post(
        "/admin/data/karaoke_songs/update",
        data={"csrf_token": admin_client.csrf, "row_token": "위조토큰", "title": "바뀌면 안 됨", "artist": "칸나"},
    )
    assert resp.status_code == 400
    assert _scalar(db, "SELECT COUNT(*) FROM karaoke_songs WHERE title = '보호되는 곡'") == 1


def test_admin_update_rejects_bad_csrf(admin_client, db, clean_db):
    target = _insert_song(db, "보호되는 곡", "칸나")
    resp = admin_client.post(
        "/admin/data/karaoke_songs/update",
        data={"csrf_token": "wrong", "row_token": serialize_row(target), "title": "바뀌면 안 됨", "artist": "칸나"},
    )
    assert resp.status_code == 400
    assert _scalar(db, "SELECT COUNT(*) FROM karaoke_songs WHERE title = '보호되는 곡'") == 1


def test_admin_update_requires_login(client, db, clean_db):
    target = _insert_song(db, "보호되는 곡", "칸나")
    resp = client.post(
        "/admin/data/karaoke_songs/update",
        data={"csrf_token": "x", "row_token": serialize_row(target), "title": "바뀌면 안 됨", "artist": "칸나"},
    )
    assert resp.status_code == 302
    assert _scalar(db, "SELECT COUNT(*) FROM karaoke_songs WHERE title = '보호되는 곡'") == 1


def test_admin_update_unknown_table_404(admin_client, clean_db):
    assert admin_client.post(
        "/admin/data/secret_table/update",
        data={"csrf_token": admin_client.csrf, "row_token": "x"},
    ).status_code == 404


def test_admin_delete_removes_song(admin_client, db, clean_db):
    target = _insert_song(db, "삭제될 곡", "칸나")
    resp = admin_client.post(
        "/admin/data/karaoke_songs/delete",
        data={"csrf_token": admin_client.csrf, "row_token": serialize_row(target)},
    )
    assert resp.status_code == 302
    assert _scalar(db, "SELECT COUNT(*) FROM karaoke_songs") == 0


def test_admin_page_lists_karaoke_sections(admin_client, db, clean_db):
    _insert_song(db, "관리자에 보이는 곡", "칸나", tj="123")
    html = admin_client.get("/admin/").get_data(as_text=True)
    assert "관리자에 보이는 곡" in html
    assert "노래방 번호" in html
    assert "/admin/data/karaoke_songs/update" in html
    assert "여러 곡 한 번에 등록하기" in html


@pytest.mark.parametrize("table_name", ["karaoke_songs", "karaoke_members", "karaoke_reports"])
def test_admin_page_offers_a_form_for_every_karaoke_table(admin_client, clean_db, table_name):
    """관리자 화면이 노래방 테이블을 모두 읽어와 양식을 그려야 한다(누락 시 경고가 뜬다)."""
    html = admin_client.get("/admin/").get_data(as_text=True)
    assert f'action="/admin/data/{table_name}"' in html
    assert "일부 테이블을 불러오지 못했습니다" not in html


# ---------- 메인 화면 버튼 노출 ----------

def test_main_buttons_api_returns_seeded_buttons(client, clean_db):
    payload = client.get("/api/main/buttons").get_json()
    assert [button["key"] for button in payload] == ["search", "karaoke", "congratulation"]
    assert all(button["visible"] is True for button in payload)


def test_main_buttons_api_reports_hidden_button(client, db, clean_db):
    with db.cursor() as cursor:
        cursor.execute("UPDATE main_buttons SET visible = FALSE WHERE button_key = 'karaoke'")
    payload = {button["key"]: button for button in client.get("/api/main/buttons").get_json()}
    assert payload["karaoke"]["visible"] is False
    assert payload["search"]["visible"] is True


def test_main_buttons_api_orders_by_display_order(client, db, clean_db):
    with db.cursor() as cursor:
        cursor.execute("UPDATE main_buttons SET display_order = 99 WHERE button_key = 'search'")
    keys = [button["key"] for button in client.get("/api/main/buttons").get_json()]
    assert keys == ["karaoke", "congratulation", "search"]


def test_admin_can_hide_a_main_button(admin_client, db, clean_db):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM main_buttons WHERE button_key = 'karaoke'")
        row = cursor.fetchone()

    resp = admin_client.post(
        "/admin/data/main_buttons/update",
        data={
            "csrf_token": admin_client.csrf, "row_token": serialize_row(row),
            "button_key": "karaoke", "label": "노래방 번호 찾기", "visible": "0", "display_order": "2",
        },
    )
    assert resp.status_code == 302
    assert _scalar(db, "SELECT visible FROM main_buttons WHERE button_key = 'karaoke'") == 0
    # 다른 버튼은 그대로여야 한다.
    assert _scalar(db, "SELECT visible FROM main_buttons WHERE button_key = 'search'") == 1


def test_main_page_marks_every_button_with_a_key(client):
    """화면의 버튼과 DB의 button_key가 어긋나면 표시 설정이 먹지 않는다."""
    html = client.get("/").get_data(as_text=True)
    for key in ("search", "karaoke", "congratulation"):
        assert f'data-button-key="{key}"' in html


# ---------- 커버 곡 발매일 채우기 ----------

def _insert_cover(db, title, video_id, release_date=None, category="cover"):
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO karaoke_songs (title, artist, section, category, release_date, youtube_video_id)"
            " VALUES (%s, %s, 'solo', %s, %s, %s)",
            (title, "테스트 가수", category, release_date, video_id),
        )
        cursor.execute("SELECT * FROM karaoke_songs WHERE title = %s", (title,))
        return cursor.fetchone()


def _release_date(db, title):
    value = _scalar(db, "SELECT release_date FROM karaoke_songs WHERE title = %s", (title,))
    return value.isoformat() if value else None


def test_backfill_fills_only_covers_missing_a_release_date(db, clean_db):
    _insert_cover(db, "발매일 없는 커버", "aaaaaaaaaaa")
    _insert_cover(db, "발매일 있는 커버", "bbbbbbbbbbb", release_date="2020-01-01")
    _insert_cover(db, "오리지널 곡", "ccccccccccc", category="original")
    _insert_cover(db, "영상 없는 커버", None)

    with patch.object(
        release_dates, "fetch_upload_dates",
        return_value={"aaaaaaaaaaa": "2024-02-03", "bbbbbbbbbbb": "2024-02-04", "ccccccccccc": "2024-02-05"},
    ) as fetch:
        stats = release_dates.backfill_release_dates()

    # 이미 발매일이 있는 곡·오리지널 곡·영상이 없는 곡은 조회 대상에서부터 빠진다.
    assert fetch.call_args.args[0] == ["aaaaaaaaaaa"]
    assert stats["updated"] == 1
    assert _release_date(db, "발매일 없는 커버") == "2024-02-03"
    assert _release_date(db, "발매일 있는 커버") == "2020-01-01"
    assert _release_date(db, "오리지널 곡") is None
    assert _release_date(db, "영상 없는 커버") is None


def test_backfill_logs_videos_it_could_not_read_and_keeps_going(db, clean_db):
    _insert_cover(db, "지워진 영상 커버", "aaaaaaaaaaa")
    _insert_cover(db, "살아 있는 영상 커버", "bbbbbbbbbbb")

    with patch.object(release_dates, "fetch_upload_dates", return_value={"bbbbbbbbbbb": "2024-03-03"}):
        stats = release_dates.backfill_release_dates()

    assert stats["updated"] == 1
    assert len(stats["missing"]) == 1
    assert "지워진 영상 커버" in stats["missing"][0]
    assert _release_date(db, "지워진 영상 커버") is None
    assert _release_date(db, "살아 있는 영상 커버") == "2024-03-03"


def test_backfill_can_overwrite_existing_release_dates(db, clean_db):
    _insert_cover(db, "덮어쓸 커버", "aaaaaaaaaaa", release_date="2020-01-01")

    with patch.object(release_dates, "fetch_upload_dates", return_value={"aaaaaaaaaaa": "2024-04-04"}):
        stats = release_dates.backfill_release_dates(overwrite=True)

    assert stats["updated"] == 1
    assert _release_date(db, "덮어쓸 커버") == "2024-04-04"


def test_backfill_dry_run_does_not_write(db, clean_db):
    _insert_cover(db, "미리보기 커버", "aaaaaaaaaaa")

    with patch.object(release_dates, "fetch_upload_dates", return_value={"aaaaaaaaaaa": "2024-05-05"}):
        stats = release_dates.backfill_release_dates(dry_run=True)

    assert stats["updated"] == 1
    assert _release_date(db, "미리보기 커버") is None


def test_backfill_accepts_a_full_url_saved_on_the_song(db, clean_db):
    _insert_cover(db, "주소로 적힌 커버", "youtu.be/aaaaaaaaaaa")

    with patch.object(release_dates, "fetch_upload_dates", return_value={"aaaaaaaaaaa": "2024-06-06"}) as fetch:
        release_dates.backfill_release_dates()

    assert fetch.call_args.args[0] == ["aaaaaaaaaaa"]
    assert _release_date(db, "주소로 적힌 커버") == "2024-06-06"


def test_admin_saves_only_the_video_id_from_a_pasted_url(admin_client, db, clean_db):
    resp = admin_client.post(
        "/admin/data/karaoke_songs",
        data={
            "csrf_token": admin_client.csrf, "title": "링크로 등록한 곡", "artist": "테스트 가수",
            "youtube_video_id": "https://www.youtube.com/watch?v=aaaaaaaaaaa&t=30",
        },
    )
    assert resp.status_code == 302
    assert _scalar(db, "SELECT youtube_video_id FROM karaoke_songs WHERE title = %s", ("링크로 등록한 곡",)) == "aaaaaaaaaaa"


def test_bulk_import_keeps_a_saved_video_when_the_pasted_table_has_none(admin_client, db, clean_db):
    """유튜브 열이 없는 표를 다시 붙여 넣어도 이미 적어 둔 영상은 지워지지 않아야 한다."""
    _insert_cover(db, "영상이 있는 곡", "aaaaaaaaaaa")
    pasted = "\t".join(["곡명", "가수", "TJ"]) + "\n" + "\t".join(["영상이 있는 곡", "테스트 가수", "12345"])

    resp = admin_client.post(
        "/admin/karaoke/import",
        data={"csrf_token": admin_client.csrf, "content": pasted},
    )
    assert resp.status_code == 302
    assert _scalar(db, "SELECT youtube_video_id FROM karaoke_songs WHERE title = %s", ("영상이 있는 곡",)) == "aaaaaaaaaaa"
    assert _scalar(db, "SELECT tj FROM karaoke_songs WHERE title = %s", ("영상이 있는 곡",)) == "12345"
