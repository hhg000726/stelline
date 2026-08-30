"""블루프린트/라우트가 전부 등록되어 있는지 확인한다. DB 불필요."""

EXPECTED_RULES = {
    # 공개 화면
    "/",
    "/search",
    "/congratulation",
    "/offline",
    "/karaoke",
    # 인증
    "/auth/login",
    "/auth/logout",
    # 관리자
    "/admin/",
    "/admin/data/<table_name>",
    "/admin/data/<table_name>/delete",
    "/admin/data/<table_name>/update",
    "/admin/karaoke/import",
    "/admin/dev/import-snapshot",
    # main API
    "/api/main/record",
    "/api/main/events",
    "/api/main/twits",
    "/api/main/buttons",
    # search API
    "/api/search/force_search",
    "/api/search/not_searched",
    "/api/search/record",
    "/api/search/songs",
    "/api/search/reports",
    # bugs API
    "/api/bugs/rank",
    # congratulation API
    "/api/congratulation/congratulations",
    "/api/congratulation/reports",
    "/api/congratulation/register",
    "/api/congratulation/unregister",
    "/api/congratulation/check-token",
    # offline API
    "/api/offline/offline_api",
    # karaoke API
    "/api/karaoke/songs",
    "/api/karaoke/reports",
    "/api/karaoke/record_copy",
}


def test_all_expected_routes_registered(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    missing = EXPECTED_RULES - rules
    assert not missing, f"등록되지 않은 라우트: {sorted(missing)}"


def test_blueprints_registered(app):
    assert set(app.blueprints) >= {"admin", "auth", "api"}
