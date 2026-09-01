"""사이트 문구·그림의 저장과 반영 (실제 MySQL).

관리자가 고친 값이 공개 API에 그대로 나오는지, 비운 값이 화면에서 사라지는지,
규격을 벗어난 값이 저장되지 않는지를 끝에서 끝까지 확인한다.
"""

import io

from tests.conftest import requires_db
from tests.test_content_units import make_png

pytestmark = requires_db


def contents(client):
    return client.get("/api/content").get_json()


def post(admin_client, key, **data):
    return admin_client.post(
        f"/admin/content/{key}",
        data={"csrf_token": admin_client.csrf, **data},
        follow_redirects=False,
    )


def upload(admin_client, key, image_bytes, filename="test.png"):
    return admin_client.post(
        f"/admin/content/{key}",
        data={
            "csrf_token": admin_client.csrf,
            "action": "save",
            "image": (io.BytesIO(image_bytes), filename),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )


# ---------------------------------------------------------------- 문구

def test_saved_text_shows_up_on_the_public_api(admin_client, clean_db):
    assert post(admin_client, "main_hero_subtitle", action="save", text="새 소개 문구").status_code == 302
    item = contents(admin_client)["main_hero_subtitle"]
    assert item["value"] == "새 소개 문구"
    assert item["hidden"] is False
    assert item["source"] == "custom"


def test_untouched_text_keeps_the_default(admin_client, clean_db):
    item = contents(admin_client)["main_bugs_note"]
    assert item["value"] == "즐겨찾기 투표 현황입니다."
    assert item["source"] == "default"


def test_cleared_text_disappears_from_the_page(admin_client, clean_db):
    post(admin_client, "main_twits_note", action="clear")
    item = contents(admin_client)["main_twits_note"]
    assert item["hidden"] is True
    assert item["value"] == ""


def test_saving_a_blank_value_is_the_same_as_clearing(admin_client, clean_db):
    post(admin_client, "main_twits_note", action="save", text="   ")
    assert contents(admin_client)["main_twits_note"]["hidden"] is True


def test_reset_brings_the_default_back(admin_client, clean_db):
    post(admin_client, "main_hero_subtitle", action="save", text="잠깐 바꾼 문구")
    post(admin_client, "main_hero_subtitle", action="reset")
    item = contents(admin_client)["main_hero_subtitle"]
    assert item["source"] == "default"
    assert item["value"] == "스텔라이브를 좋아해서 만든 비공식 팬 사이트입니다."


def test_text_over_the_limit_is_refused_by_the_server(admin_client, clean_db):
    """화면에서 글자 수를 세어 주지만, 그 검사를 건너뛰고 보내도 서버가 막는다."""
    resp = post(admin_client, "main_bugs_note", action="save", text="가" * 200)
    assert resp.status_code == 302
    assert contents(admin_client)["main_bugs_note"]["source"] == "default"


def test_pasted_newlines_do_not_stretch_a_one_line_slot(admin_client, clean_db):
    post(admin_client, "main_bugs_note", action="save", text="첫 줄\n둘째 줄")
    assert contents(admin_client)["main_bugs_note"]["value"] == "첫 줄 둘째 줄"


def test_multiline_item_keeps_its_lines(admin_client, clean_db):
    post(admin_client, "search_help_list", action="save", text="첫째\n\n둘째\n")
    assert contents(admin_client)["search_help_list"]["value"] == "첫째\n둘째"


def test_unknown_key_is_rejected(admin_client, clean_db):
    assert post(admin_client, "not_a_real_key", action="save", text="x").status_code == 404


def test_saving_without_csrf_is_rejected(admin_client, clean_db):
    resp = admin_client.post("/admin/content/main_bugs_note", data={"text": "몰래 바꾸기"})
    assert resp.status_code == 400
    assert contents(admin_client)["main_bugs_note"]["source"] == "default"


def test_saving_requires_login(client, clean_db):
    resp = client.post("/admin/content/main_bugs_note", data={"text": "로그인 없이"}, follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


# ---------------------------------------------------------------- 그림

def test_uploaded_image_is_served_and_linked(admin_client, clean_db):
    assert upload(admin_client, "search_step_pc_1_image", make_png(640, 360)).status_code == 302

    item = contents(admin_client)["search_step_pc_1_image"]
    assert item["source"] == "custom"
    assert item["value"].startswith("/api/content/image/search_step_pc_1_image?v=")

    served = admin_client.get(item["value"])
    assert served.status_code == 200
    assert served.mimetype == "image/png"
    assert served.headers["X-Content-Type-Options"] == "nosniff"


def test_untouched_image_keeps_the_file_shipped_with_the_site(admin_client, clean_db):
    assert contents(admin_client)["search_step_pc_1_image"]["value"] == "/search/1.PNG"


def test_cleared_image_disappears_from_the_page(admin_client, clean_db):
    post(admin_client, "search_step_pc_2_image", action="clear")
    assert contents(admin_client)["search_step_pc_2_image"]["hidden"] is True


def test_reset_brings_the_original_picture_back(admin_client, clean_db):
    upload(admin_client, "search_step_pc_3_image", make_png(640, 360))
    post(admin_client, "search_step_pc_3_image", action="reset")
    assert contents(admin_client)["search_step_pc_3_image"]["value"] == "/search/3.PNG"


def test_a_file_that_is_not_an_image_is_refused(admin_client, clean_db):
    """이름만 .png 인 파일은 앞머리를 보고 걸러낸다."""
    upload(admin_client, "search_step_pc_1_image", b"<svg><script>alert(1)</script></svg>", "sneaky.png")
    assert contents(admin_client)["search_step_pc_1_image"]["source"] == "default"


def test_an_image_with_a_broken_aspect_is_refused(admin_client, clean_db):
    """공지 그림은 16:9 칸을 채우므로, 세로로 긴 그림은 받지 않는다."""
    upload(admin_client, "main_notice_image", make_png(500, 500))
    assert contents(admin_client)["main_notice_image"]["hidden"] is True


def test_an_image_that_is_too_small_is_refused(admin_client, clean_db):
    upload(admin_client, "search_step_pc_1_image", make_png(100, 60))
    assert contents(admin_client)["search_step_pc_1_image"]["source"] == "default"


def test_a_text_item_does_not_accept_an_image(admin_client, clean_db):
    upload(admin_client, "main_hero_subtitle", make_png(640, 360))
    assert contents(admin_client)["main_hero_subtitle"]["source"] == "default"


def test_missing_image_returns_404_so_the_page_falls_back(admin_client, clean_db):
    assert admin_client.get("/api/content/image/main_notice_image").status_code == 404


def test_replacing_an_image_changes_its_address(admin_client, clean_db):
    """주소가 그대로면 브라우저가 예전 그림을 계속 보여 준다."""
    upload(admin_client, "main_notice_image", make_png(640, 360))
    first = contents(admin_client)["main_notice_image"]
    upload(admin_client, "main_notice_image", make_png(800, 450))
    second = contents(admin_client)["main_notice_image"]
    assert second["width"] == 800
    assert admin_client.get(second["value"]).status_code == 200
    assert first["value"] != second["value"] or first["width"] != second["width"]


# ---------------------------------------------------------------- 관리자 화면

def test_admin_page_lists_every_editable_item(admin_client, clean_db):
    html = admin_client.get("/admin/").get_data(as_text=True)
    assert 'data-group-panel="content"' in html
    assert 'id="content-main_hero_subtitle"' in html
    assert 'id="content-search_step_pc_1_image"' in html
    # 저장 전 미리보기와 글자 수 세기가 화면에 있어야 한다.
    assert "data-content-preview-text" in html
    assert "data-content-counter" in html
    assert "data-content-filecheck" in html


def test_admin_page_marks_which_items_were_changed(admin_client, clean_db):
    post(admin_client, "main_hero_subtitle", action="save", text="바뀐 문구")
    post(admin_client, "main_twits_note", action="clear")
    html = admin_client.get("/admin/").get_data(as_text=True)
    assert "바뀐 문구" in html
    assert "수정됨" in html
    assert "비움" in html
