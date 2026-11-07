"""화면(SPA 문서·정적 자원·서버 템플릿) 제공을 검증한다. DB 불필요.

공개 화면은 React 한 벌(SPA)이다. 서버는 어느 주소로 들어오든 같은 문서를 내려주고,
무엇을 그릴지는 브라우저가 정한다. 그래서 여기서 보는 것은 두 가지다.

  1. 서버가 제 몫을 하는가 - 주소마다 문서를 주는가, 없는 주소는 404인가,
     빌드 결과물이 실제로 저장소에 들어 있는가(배포 서버에는 Node가 없다).
  2. 화면 코드가 예전 규칙을 그대로 지키는가 - 예전에는 화면별 .js 파일을 읽어 확인했다.
     지금은 같은 규칙이 frontend/src 아래에 있으므로 그쪽을 읽는다.
"""

import json
import pathlib
import re

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND_SRC = PROJECT_ROOT / "frontend" / "src"
STATIC_ROOT = PROJECT_ROOT / "stelline" / "static"

PAGE_PATHS = [
    "/",
    "/search",
    "/search/",
    "/congratulation",
    "/congratulation/",
    "/offline",
    "/offline/",
    "/karaoke",
    "/karaoke/",
]


def source(*parts):
    """frontend/src 아래 파일 하나를 글자로 읽는다."""
    return FRONTEND_SRC.joinpath(*parts).read_text(encoding="utf-8")


# --- 서버가 내려주는 것 -----------------------------------------------------

@pytest.mark.parametrize("path", PAGE_PATHS)
def test_public_pages_render(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
    assert b"<!DOCTYPE html>" in resp.data or b"<!doctype html>" in resp.data


@pytest.mark.parametrize("path", PAGE_PATHS)
def test_every_page_serves_the_same_app_shell(client, path):
    """주소를 직접 치고 들어와도(딥링크) 같은 문서가 와야 화면이 열린다."""
    assert client.get(path).data == client.get("/").data


def test_app_shell_loads_the_built_bundle(client):
    """빌드 결과물은 저장소에 커밋한다(배포 서버에 Node를 두지 않기 위해서다).

    문서가 가리키는 파일이 실제로 없으면 화면이 통째로 빈다. 빌드를 잊고 올린 경우가
    여기서 걸린다.
    """
    html = client.get("/").get_data(as_text=True)
    refs = re.findall(r'(?:src|href)="(/app/[^"]+)"', html)
    assert refs, "문서가 빌드된 번들을 가리키지 않습니다. `npm run build` 를 실행하세요."
    for ref in refs:
        assert client.get(ref).status_code == 200, ref


def test_theme_is_decided_before_the_page_is_painted(client):
    """본문 뒤에서 배색을 정하면 밝은 화면이 한 번 번쩍인다."""
    head = client.get("/").get_data(as_text=True).split("</head>")[0]
    assert "stelline.theme" in head
    assert "prefers-color-scheme" in head
    assert 'setAttribute("data-theme"' in head


@pytest.mark.parametrize(
    "path",
    [
        # 서버가 그리는 관리자·로그인 화면이 함께 쓰는 공용 배색과 다크 모드.
        "/assets/site.css",
        "/assets/theme.js",
        # 화면과 무관하게 그대로 남아야 하는 것들.
        "/firebase-messaging-sw.js",
        "/search/1.PNG",
        "/search/1.jpg",
        "/favicon.svg",
    ],
)
def test_static_assets_served(client, path):
    assert client.get(path).status_code == 200


def test_unknown_path_returns_404(client):
    resp = client.get("/definitely/not/here")
    assert resp.status_code == 404


def test_deployment_nginx_forwards_vercel_origin_requests_to_the_app():
    config = (PROJECT_ROOT / "deploy" / "nginx" / "stelline.conf").read_text(encoding="utf-8")
    server_blocks = re.findall(r"(?ms)^server \{\n(.*?)(?=^server \{|\Z)", config)
    vercel_server = next(
        (block for block in server_blocks if "server_name 168.107.1.195 stel-line.vercel.app;" in block),
        None,
    )

    assert vercel_server is not None
    assert "listen 80;" in vercel_server
    assert "try_files $uri $uri/ @app;" in vercel_server
    assert "location @app" in vercel_server
    assert "location /api/" in vercel_server
    assert "location /admin" in vercel_server
    assert "location /auth" in vercel_server
    assert "proxy_pass http://stelline_app;" in vercel_server
    assert "return 404;" in next(block for block in server_blocks if "listen 80 default_server;" in block)




def test_deployment_nginx_serves_only_through_vercel_without_certificates():
    """공개 주소는 Vercel 하나다. 서버에는 인증서가 없으므로, 인증서 경로나 다른 이름의 server 블록을
    적어 두면 nginx -t 가 실패해 배포가 통째로 막히거나 쓰지 않는 주소가 다시 열린다."""
    config = (PROJECT_ROOT / "deploy" / "nginx" / "stelline.conf").read_text(encoding="utf-8")
    directives = "\n".join(line for line in config.splitlines() if not line.lstrip().startswith("#"))
    server_names = {name for line in re.findall(r"server_name ([^;]+);", directives) for name in line.split()}
    assert server_names == {"168.107.1.195", "stel-line.vercel.app", "_"}
    assert "ssl_certificate" not in directives
    assert "listen 443" not in directives

def test_hashed_bundles_are_cached_for_good_and_the_shell_is_not():
    """/app/ 을 오래 캐시해도 되는 것은 이름에 내용 해시가 붙어 있기 때문이다.

    해시 없는 파일이 그 폴더에 들어오면, 고쳐도 방문자 브라우저에는 1년 동안 옛것이 남는다.
    """
    bundle_names = [path.name for path in (PROJECT_ROOT / "stelline" / "static" / "app").iterdir()]
    assert bundle_names
    unhashed = [name for name in bundle_names if not re.fullmatch(r"[\w.]+-[\w-]{8}\.(js|css)", name)]
    assert not unhashed, f"해시 없는 번들: {unhashed}"

    config = (PROJECT_ROOT / "deploy" / "nginx" / "stelline.conf").read_text(encoding="utf-8")
    server_blocks = re.findall(r"(?ms)^server \{\n(.*?)(?=^server \{|\Z)", config)
    app_servers = [block for block in server_blocks if "@app" in block]
    assert len(app_servers) == 1
    for block in app_servers:
        bundle_rule = re.search(r"(?s)location /app/ \{(.*?)\}", block).group(1)
        assert "immutable" in bundle_rule
        assert "try_files $uri =404;" in bundle_rule
        shell_rule = re.search(r"(?s)location / \{(.*?)\}", block).group(1)
        assert 'Cache-Control "no-cache"' in shell_rule


def test_production_process_is_supervised_single_worker_and_local_only():
    """운영 앱은 systemd 가 워커 하나로, 서버 안쪽 주소에만 띄운다.

    워커가 여럿이면 백그라운드 작업이 겹치고, 0.0.0.0 이면 nginx 를 건너뛴 길이 열리며,
    nohup 으로 띄우면 죽었을 때 다음 배포까지 502다.
    """
    unit = (PROJECT_ROOT / "deploy" / "systemd" / "stelline.service").read_text(encoding="utf-8")
    exec_start = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
    assert "/home/ubuntu/stelline/venv/bin/gunicorn" in exec_start
    assert "--workers 1" in exec_start
    assert "--bind 127.0.0.1:5000" in exec_start
    assert "Restart=always" in unit
    assert "WorkingDirectory=/home/ubuntu/stelline" in unit

    script = (PROJECT_ROOT / "deploy" / "deploy.sh").read_text(encoding="utf-8")
    commands = [line.strip() for line in script.splitlines() if line.strip() and not line.strip().startswith("#")]
    assert "sudo systemctl restart stelline" in commands
    # 준비 단계가 실패하면 재시작 전에 멈춰야 한다(마이그레이션 실패를 초록 배포로 덮지 않게).
    assert commands.index("set -eo pipefail") < commands.index("sudo systemctl restart stelline")
    assert not any(command.startswith(("pkill", "nohup")) for command in commands)

    nginx = (PROJECT_ROOT / "deploy" / "nginx" / "stelline.conf").read_text(encoding="utf-8")
    assert set(re.findall(r"proxy_pass (\S+);", nginx)) == {"http://stelline_app"}


def test_nginx_sends_requests_to_the_standby_only_while_the_main_server_is_down():
    """평소에는 본 서버(5000)만 받는다. 본 서버가 연결을 거절하면(재시작·장애) 같은 요청을 대기 서버(5001)로 넘긴다."""
    nginx = (PROJECT_ROOT / "deploy" / "nginx" / "stelline.conf").read_text(encoding="utf-8")
    upstream = re.search(r"(?s)upstream stelline_app \{(.*?)\}", nginx).group(1)
    servers = re.findall(r"^\s*server (\S+)([^;]*);", upstream, re.M)
    assert servers == [("127.0.0.1:5000", " max_fails=1 fail_timeout=10s"), ("127.0.0.1:5001", " backup")]
    # 다음 서버로 넘기는 조건을 좁히지 않는다(기본값 error timeout 이 연결 거절을 받아 넘긴다).
    directives = [line for line in nginx.splitlines() if not line.lstrip().startswith("#")]
    assert not any("proxy_next_upstream" in line for line in directives)


def test_standby_server_runs_the_same_app_without_background_tasks():
    """대기 서버는 같은 코드·같은 .env 로 5001 에 떠 있기만 한다.

    백그라운드 작업을 함께 돌리면 대기 서버가 먼저 잠금을 잡았을 때 작업 로그가 본 서버의 logs/ 에 남지 않아
    관리자 화면 '운영 로그'가 빈다. 로그를 같은 폴더에 쌓으면 두 프로세스가 저마다 자정에 파일을 넘기며 서로 덮어쓴다.
    """
    main_unit = (PROJECT_ROOT / "deploy" / "systemd" / "stelline.service").read_text(encoding="utf-8")
    standby = (PROJECT_ROOT / "deploy" / "systemd" / "stelline-standby.service").read_text(encoding="utf-8")
    exec_start = next(line for line in standby.splitlines() if line.startswith("ExecStart="))
    assert exec_start == next(line for line in main_unit.splitlines() if line.startswith("ExecStart=")).replace(
        "127.0.0.1:5000", "127.0.0.1:5001"
    )
    assert "Environment=START_BACKGROUND_TASKS=false" in standby
    assert "Environment=LOG_DIR=/home/ubuntu/stelline/logs/standby" in standby
    for line in ("WorkingDirectory=/home/ubuntu/stelline", "Restart=always", "User=ubuntu"):
        assert line in standby


def test_deploy_restarts_the_standby_first_and_the_main_server_last():
    """새 코드는 대기 서버에서 먼저 확인한다. 뜨지 않으면 본 서버는 손대지 않아 옛 코드로 계속 받는다.
    본 서버를 다시 띄우는 몇 초 동안은 대기 서버가 받는다. 대기 서버를 설치하기 전에는 본 서버만 다시 띄운다."""
    script = (PROJECT_ROOT / "deploy" / "deploy.sh").read_text(encoding="utf-8")
    commands = [line.strip() for line in script.splitlines() if line.strip() and not line.strip().startswith("#")]
    standby_branch = commands[commands.index("if systemctl cat stelline-standby.service >/dev/null 2>&1; then"):
                              commands.index("else")]
    assert [c for c in standby_branch if c.startswith(("sudo systemctl restart", "wait_until_up"))] == [
        "sudo systemctl restart stelline-standby",
        "wait_until_up stelline-standby 5001",
        "sudo systemctl restart stelline",
        "wait_until_up stelline 5000",
    ]
    after_else = commands[commands.index("else"):]
    fallback = after_else[:after_else.index("fi")]
    assert "sudo systemctl restart stelline" in fallback and "wait_until_up stelline 5000" in fallback
    # 마이그레이션은 두 서버를 다시 띄우기 전에 한 번만 한다.
    assert commands.index("python -m stelline.database.migrate") < commands.index("sudo systemctl restart stelline-standby")

def test_removed_frontend_files_are_gone(client):
    """예전 화면 파일이 남아 있으면 어느 쪽이 진짜인지 알 수 없다."""
    for path in ("/index.js", "/assets/site.js", "/assets/nav.js", "/assets/content.js",
                 "/search/search.js", "/karaoke/karaoke.js", "/offline/offline.js"):
        assert client.get(path).status_code == 404, path


def test_login_page_renders(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert "관리자" in resp.get_data(as_text=True)


def test_admin_requires_login(client):
    resp = client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_logout_redirects_to_login(client):
    resp = client.get("/auth/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_login_rejects_bad_credentials(client):
    resp = client.post(
        "/auth/login",
        data={"username": "admin", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 200  # 리다이렉트 없이 로그인 화면 재표시
    assert "로그인 실패" in resp.get_data(as_text=True)
    with client.session_transaction() as sess:
        assert "logged_in" not in sess


def test_login_accepts_configured_credentials(client):
    resp = client.post(
        "/auth/login",
        data={"username": "admin", "password": "test-admin-password"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/admin" in resp.headers["Location"]
    with client.session_transaction() as sess:
        assert sess.get("logged_in") is True


# --- 화면 사이 이동 ---------------------------------------------------------

def test_pages_move_without_reloading_the_document():
    """링크마다 문서를 다시 받으면 흰 화면이 한 번 번쩍이고 받아 둔 것도 다 버린다."""
    app = source("App.jsx")
    for path in ("/", "/search", "/karaoke", "/congratulation", "/offline"):
        assert f'path="{path}"' in app, path
    # 화면 묶음은 들어간 화면 것만 받아 온다(React.lazy 는 pages.js 가 감싼다).
    assert "PAGES[" in app
    assert "lazy(" in source("pages.js")
    assert "Suspense" in source("components", "Layout.jsx")


def test_moving_between_pages_shows_that_something_is_loading():
    """아무 표시 없이 멈춰 있으면 눌린 건지 고장인지 알 수 없다."""
    loading = source("components", "Loading.jsx")
    assert "RouteProgress" in loading
    assert "Skeleton" in loading
    assert "RouteFallback" in source("components", "Layout.jsx")


def test_one_screen_falling_over_does_not_empty_the_site():
    """한 문서 안에서 화면을 바꾸므로, 막지 않으면 사고 하나가 사이트를 통째로 지운다."""
    assert "ErrorBoundary" in source("components", "Layout.jsx")
    assert "getDerivedStateFromError" in source("components", "ErrorBoundary.jsx")


def test_every_page_menu_follows_the_admin_button_settings():
    """숨긴 기능이 어느 화면에는 남아 있으면 안 된다. 메뉴는 모두 같은 설정을 따른다."""
    nav = source("context", "NavButtonsContext.jsx")
    assert "main/buttons" in nav
    items = source("components", "navItems.js")
    for key in ("search", "karaoke", "congratulation", "offline"):
        assert f'key: "{key}"' in items
    # 머리말 메뉴와 메인 화면 카드가 같은 목록·같은 설정을 쓴다.
    assert "useNavItems" in source("components", "SiteHeader.jsx")
    assert "useNavItems" in source("pages", "MainPage.jsx")


def test_sub_pages_link_to_every_other_screen():
    """화면마다 '메인으로'만 있으면 기능 사이를 오가려면 메인을 거쳐야 한다."""
    header = source("components", "SiteHeader.jsx")
    assert 'className="site-nav"' in header
    # NavLink 는 지금 보고 있는 화면에 aria-current="page" 를 스스로 붙인다.
    assert "NavLink" in header
    # 메인 화면에는 큰 제목과 기능 카드가 따로 있어 이 줄을 두지 않는다.
    assert 'location.pathname !== "/"' in source("components", "Layout.jsx")


# --- 노래방 화면 ------------------------------------------------------------

def test_karaoke_mode_is_gone():
    """어두운 배색은 전역 다크 모드가 맡으므로 노래방 모드는 없앴다."""
    assert "karaoke-mode" not in source("styles", "karaoke.css")
    assert "노래방 모드" not in source("pages", "KaraokePage.jsx")


def test_karaoke_page_offers_the_new_controls():
    page = source("pages", "KaraokePage.jsx")
    assert 'value: "and"' in source("pages", "karaoke", "FilterPanel.jsx")  # 필터 AND 옵션
    assert 'id="pick-favorite"' in source("pages", "karaoke", "PickDialog.jsx")
    assert 'id="pick-setlist"' in source("pages", "karaoke", "PickDialog.jsx")
    assert "PickDialog" in page


def test_karaoke_multi_pick_extends_the_random_pick():
    """랜덤 한 곡을 여러 곡으로 늘렸다. 뽑을 곡 수를 정하고, 같은 필터에서 표본을
    뽑으며, 낱개로 빼거나 목록째 즐겨찾기·부를 곡에 담을 수 있다."""
    page = source("pages", "KaraokePage.jsx")
    dialog = source("pages", "karaoke", "MultiPickDialog.jsx")
    assert "MultiPickDialog" in page
    assert 'id="random-pick-multi"' in page
    assert "sampleSongs" in source("pages", "karaoke", "search.js")
    # 뽑을 곡 수 지정
    assert 'id="multi-pick-count"' in dialog
    # 개별 삭제 + 전체 담기
    assert 'id="multi-pick-favorite-all"' in dialog
    assert 'id="multi-pick-setlist-all"' in dialog
    assert "onRemove" in dialog
    # 랜덤 한 곡은 그대로 남는다.
    assert 'id="random-pick"' in page


def test_karaoke_list_is_shown_in_pages():
    """곡이 수백 개라 한 번에 다 그리면 스크롤 막대가 실낱같이 얇아진다."""
    page = source("pages", "KaraokePage.jsx")
    assert 'id="load-more"' in page
    assert "PAGE_SIZE" in source("pages", "karaoke", "constants.js")
    assert "setShownCount(PAGE_SIZE)" in page


def test_karaoke_page_sorts_randomly_or_by_name():
    """정렬 기준으로 삼을 만한 날짜·순서 값을 두지 않아, 랜덤순과 가나다순만 남겼다."""
    page = source("pages", "KaraokePage.jsx")
    assert '<option value="random">랜덤순</option>' in page
    assert '<option value="title">가나다순</option>' in page
    for gone in ("최신순", "오래된순", "번호순", "기본순"):
        assert gone not in page


def test_karaoke_keeps_what_you_are_looking_at_in_the_address():
    """새로 고쳐도, 링크를 건네줘도 같은 목록이 나와야 한다."""
    filters = source("pages", "karaoke", "filters.js")
    for name in ("q", "machine", "sort", "match", "member", "section", "category", "numbered", "fav"):
        assert f'"{name}"' in filters, name
    assert "initFilters" in filters and "filtersToParams" in filters


# --- 조회수 축하 화면 -------------------------------------------------------

def test_congratulation_badge_marks_exact_milestones_only():
    """배지 색은 100만·1000만 '단위'로 딱 떨어질 때만 바뀐다.

    예전에는 100만을 넘기기만 하면 계속 파란 배지가 붙어, 120만과 100만이 같아 보였다.
    """
    page = source("pages", "CongratulationPage.jsx")
    assert "function milestoneTier" in page
    # 나머지 연산으로 '단위'를 판정한다(이상/초과가 아니다).
    assert "tenThousands % 1000 === 0" in page
    assert "tenThousands % 100 === 0" in page
    assert "tenThousands >= 1000" not in page
    assert "tenThousands >= 100" not in page


def test_open_page_notifications_read_what_the_server_sends():
    """서버는 제목·내용을 notification 이 아니라 data 에 담아 보낸다(background_tasks/monitoring.py).

    화면을 열어 둔 사람의 알림이 notification 만 읽으면 늘 '새 알림 / 내용 없음'이 뜬다.
    서비스 워커(화면을 닫아 둔 사람)와 같은 자리에서 읽어야 한다.
    """
    worker = (STATIC_ROOT / "firebase-messaging-sw.js").read_text(encoding="utf-8")
    hook = source("pages", "congratulation", "useNotifications.js")
    for key in ("payload.data?.title", "payload.data?.body"):
        assert key in worker
        assert key in hook


# --- 불러오기·보내기 실패 ---------------------------------------------------

def test_failed_lists_show_an_error_instead_of_a_broken_card():
    """실패 응답({"error": …})을 목록으로 받으면 오류 문구 한 줄이 카드 한 장으로 그려진다.

    화면이 데이터를 받는 길은 getJson 하나이고, 실패 응답은 거기서 실패로 넘긴다.
    """
    assert "if (!response.ok) throw" in source("lib", "api.js")
    assert "getJson(path)" in source("lib", "useApiList.js")
    # 오프라인 화면은 서버 실패를 '진행 중인 이벤트가 없다'로 잘못 말하지 않는다.
    assert 'getJson("offline/offline_api")' in source("pages", "OfflinePage.jsx")


def test_report_errors_do_not_show_a_json_parse_message():
    """배포 중 502처럼 HTML 이 오는 실패에서 "Unexpected token '<'" 가 그대로 보이면 안 된다."""
    assert ".json().catch(" in source("lib", "api.js")


def test_a_script_that_failed_once_can_be_loaded_again():
    """실패한 태그가 남아 있으면 다시 부를 때 그 태그의 load 를 기다리다 캡차·지도가 영영 뜨지 않는다."""
    assert "script.remove()" in source("lib", "loadScript.js")


# --- 첫 화면과 화면 이동의 기다림 -------------------------------------------

def _early_fetch_table():
    """문서 머리의 미리 부르기 표(주소 → API)를 읽는다."""
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    table = re.search(r"var pageData = (\{.*?\});", html, re.S).group(1)
    common = re.search(r"\[([^\]]*)\]\.concat\(pageData", html).group(1)
    pages = {route: re.findall(r'"([^"]+)"', keys) for route, keys in re.findall(r'"(/[a-z]*)": \[([^\]]*)\]', table)}
    return re.findall(r'"([^"]+)"', common), pages


PAGE_SOURCES = {
    "/": [("pages", "main", "TwitsPanel.jsx"), ("pages", "main", "EventsPanel.jsx"), ("pages", "main", "BugsPanel.jsx")],
    "/search": [("pages", "SearchPage.jsx")],
    "/karaoke": [("pages", "KaraokePage.jsx")],
    "/congratulation": [("pages", "CongratulationPage.jsx")],
    "/offline": [("pages", "OfflinePage.jsx")],
}


def test_the_document_starts_each_page_s_data_with_the_bundle():
    """데이터가 번들을 다 받고 실행한 뒤에야 출발했다. 문서 머리가 미리 부르고 화면이 그것을 꺼내 쓴다.

    표와 화면이 어긋나면 같은 요청이 두 번 나가거나(꺼내 쓰지 않음) 미리 부르기가 헛돈다.
    """
    common, pages = _early_fetch_table()
    assert set(pages) == set(PAGE_SOURCES)
    assert common == ["content", "main/buttons"]
    assert 'getJson("content")' in source("context", "ContentContext.jsx")
    assert 'getJson("main/buttons")' in source("context", "NavButtonsContext.jsx")
    for route, keys in pages.items():
        text = "".join(source(*parts) for parts in PAGE_SOURCES[route])
        for key in keys:
            assert f'getJson("{key}")' in text or f'useApiList("{key}"' in text, (route, key)
    # 무언가를 바꾸는 요청(기록·제보)은 미리 부르지 않는다. 화면이 실제로 쓸 때만 나가야 한다.
    for keys in [common, *pages.values()]:
        assert not any(key.endswith(("record", "reports", "record_copy")) for key in keys)
    # 미리 부른 응답은 한 번만, 오래되지 않았을 때만 쓴다.
    api_js = source("lib", "api.js")
    assert "delete store[key]" in api_js
    assert "EARLY_MAX_AGE_MS" in api_js


def test_the_built_document_preloads_the_page_it_was_opened_on(client):
    """화면 조각은 번들을 실행한 뒤에야 출발했다. 빌드 때 '주소 → 조각' 표를 문서에 적어 함께 받는다."""
    html = client.get("/").get_data(as_text=True)
    assert "__STELLINE_ROUTE_FILES__" not in html
    table = json.loads(re.search(r"var routeFiles = (\{.*?\});", html).group(1))
    assert set(table) == set(PAGE_SOURCES)
    for route, files in table.items():
        assert files, route
        for href in files:
            assert href.startswith("/app/"), href
            assert client.get(href).status_code == 200, href
    # 실제로 부를 때(Vite)와 crossorigin 이 같아야 같은 파일을 두 번 받지 않는다.
    assert 'link.crossOrigin = ""' in html


def test_early_fetching_does_not_wait_for_the_font_stylesheet(client):
    """문서 안의 스크립트는 앞에 놓인 CSS 를 다 받을 때까지 실행되지 않는다. 다른 사이트의 글꼴 CSS 뒤에 두면
    미리 부르기가 그만큼 늦게 출발한다(운영에서 48ms, 휴대폰에서는 더 길다)."""
    head = client.get("/").get_data(as_text=True).split("</head>")[0]
    assert head.index("window.__stellineEarly") < head.index("fonts.googleapis.com/css2")
    assert head.index('setAttribute("data-theme"') < head.index("fonts.googleapis.com/css2")


def test_the_document_shows_a_skeleton_before_the_bundle_runs(client):
    """번들을 받는 동안 빈 바탕만 보이면 멈춘 것처럼 보인다."""
    root = client.get("/").get_data(as_text=True).split('<div id="root">')[1].split("</body>")[0]
    assert "skeleton" in root
    assert 'aria-hidden="true"' in root


def test_moving_to_a_page_does_not_wait_once_it_has_been_fetched():
    """미리 받은 화면은 기다리지 않고 그린다. 다만 화면을 연 동안에는 처음 고른 것을 끝까지 쓴다."""
    pages = source("pages.js")
    assert "useState(() => loaded || Waiting)" in pages
    assert "prefetchPagesWhenIdle" in source("components", "Layout.jsx")
    # 데이터를 아끼는 설정·느린 연결에서는 미리 받지 않는다.
    assert "saveData" in pages
    for parts in (("components", "SiteHeader.jsx"), ("pages", "MainPage.jsx")):
        assert "prefetchProps(item.to)" in source(*parts)


def test_a_new_deploy_reloads_once_instead_of_breaking_the_page():
    """배포로 조각 이름이 바뀌면 열어 둔 화면이 옛 조각을 못 찾는다. 한 번만 새로 고친다."""
    pages = source("pages.js")
    assert "window.location.reload()" in pages
    assert "RELOAD_GUARD_MS" in pages  # 연달아 실패하면 끝없이 새로 고치지 않는다
    # 그래도 실패하면 오류 화면에서 바로 새로 고칠 수 있게 한다.
    assert "window.location.reload()" in source("components", "ErrorBoundary.jsx")


# --- 복사·알림 말풍선 -------------------------------------------------------

def test_copy_and_toast_helpers_live_in_one_place():
    """복사 실패 처리와 말풍선은 화면마다 따로 두면 조금씩 어긋난다."""
    clipboard = source("lib", "clipboard.js")
    assert "copyText" in clipboard
    # https 가 아니거나 권한이 막힌 곳을 위한 대체 복사 경로.
    assert "execCommand" in clipboard
    assert "site-toast" in source("context", "ToastContext.jsx")


@pytest.mark.parametrize(
    "parts",
    [("pages", "KaraokePage.jsx"), ("pages", "SearchPage.jsx"), ("pages", "main", "TwitsPanel.jsx")],
)
def test_screens_use_the_shared_copy_helper(parts):
    """사본이 남아 있으면 복사 실패 처리가 화면마다 어긋난다."""
    text = source(*parts)
    assert "copyText" in text
    assert "execCommand" not in text


@pytest.mark.parametrize(
    "parts",
    [("pages", "main", "TwitsPanel.jsx"), ("pages", "SearchPage.jsx")],
)
def test_copy_failures_are_reported_instead_of_doing_nothing(parts):
    """복사가 막히면 예전에는 아무 일도 일어나지 않아 눌러도 반응이 없었다."""
    text = source(*parts)
    assert "복사하지 못했어요" in text
    # 복사를 못 했으면 붙여 넣을 것이 없으므로 바깥 사이트로 보내지 않는다.
    assert "navigator.clipboard.writeText" not in text


@pytest.mark.parametrize(
    "parts",
    [("pages", "main", "TwitsPanel.jsx"), ("pages", "SearchPage.jsx")],
)
def test_blocked_new_tabs_explain_adguard_and_popup_settings(parts):
    """PC에서 애드가드가 새 탭을 막을 때 확인할 설정도 안내한다."""
    text = source(*parts)
    assert "PC에서 애드가드를 쓰면" in text
    assert "팝업을 허용해 주세요" in text


# --- 바깥 사이트로 나가는 자리는 링크로 -------------------------------------

def test_outbound_targets_are_links_not_buttons():
    """버튼으로 두면 새 탭으로 열기·주소 미리보기 같은 것이 전부 막힌다."""
    congrats = source("pages", "CongratulationPage.jsx")
    assert '<a\n      className="card is-link"' in congrats
    assert 'target="_blank"' in congrats
    assert "window.location.href" not in congrats

    events = source("pages", "main", "EventsPanel.jsx")
    assert '<a className="btn-secondary"' in events
    assert 'target: "_blank"' in events


# --- 검색 화면의 탭 ---------------------------------------------------------

def test_search_tabs_are_wired_for_keyboard_and_screen_readers():
    """role=tab 을 붙여 둔 이상 화살표로 옮겨 다닐 수 있어야 한다."""
    tabs = source("components", "Segmented.jsx")
    assert "aria-controls" in tabs
    assert "tabpanel" in tabs
    assert "ArrowRight" in tabs and "ArrowLeft" in tabs


def test_search_steps_open_on_the_tab_matching_the_device():
    """휴대폰으로 들어온 사람에게 PC 화면 그림부터 보여 주지 않는다."""
    page = source("pages", "SearchPage.jsx")
    assert "defaultMethodTab" in page
    assert "pointer: coarse" in page


def test_search_page_keeps_the_three_tabs_and_filters_by_the_server_judgment():
    """탭은 예전 그대로(지금 막힘·최근 7일·cover 검색으로 발견)이고, 어느 곡이 들어갈지는 서버 판정
    (history.py 의 state·recent)으로만 거른다. 화면에서 따로 판정하지 않는다."""
    page = source("pages", "SearchPage.jsx")
    assert 'getJson("search/status")' in page
    for name, label in (("current", "지금 막힘"), ("recent", "최근 7일"), ("cover", "cover 검색으로 발견")):
        assert f'name: "{name}", label: "{label}"' in page
    assert 'pick: (song) => song.state === "blocked"' in page
    assert "pick: (song) => song.recent === true" in page
    assert 'pick: (song) => song.state === "cover_only"' in page
    assert "cover를 붙여야 검색돼요" in page
    assert "song.fallback_query" in page


def test_search_runs_open_their_song_lists_on_hover_or_tap():
    """'마지막 검색'·'다음 검색' 칩을 펼치면 그 회차의 곡이 나온다. 다음 검색은 서버가 정한 최소·최대 목록."""
    page = source("pages", "SearchPage.jsx")
    pill = source("pages", "search", "RunPill.jsx")
    assert "status.lastRun" in page and "status.nextRun" in page
    assert "onMouseEnter" in pill and "aria-expanded" in pill and '"Escape"' in pill
    assert "nextRun.sure" in pill and "최소 목록" in pill and "최대 목록" in pill


def test_search_page_takes_the_schedule_from_the_server():
    """검색 간격을 화면에 글자로 적어 두면 설정을 바꿀 때 어긋난다. 서버가 주는 값만 쓴다."""
    page = source("pages", "SearchPage.jsx")
    assert "schedule.interval_hours" in page and "status.nextRun.at" in page
    assert not re.search(r"\d+시간마다", page)
    defaults = source("lib", "contentDefaults.js")
    assert not re.search(r"\d+시간마다", defaults)


def test_search_cards_show_the_record_behind_the_judgment():
    page = source("pages", "SearchPage.jsx")
    assert "function WeekRecord" in page
    assert "week.results" in page
    assert "song.checked_at" in page
    # '최근 7일' 탭에는 지금 상태가 섞여 있어 카드마다 지금 상태를 적는다.
    recent_start = page.index('tabPanelProps("song-tabs", "recent", songTab === "recent")')
    assert "showState" in page[recent_start:page.index("</div>", recent_start)]


def test_search_cover_explanation_is_scoped_to_its_tabpanel():
    page = source("pages", "SearchPage.jsx")
    assert 'noteKey="search_songs_note"' not in page
    cover_panel_start = page.index('tabPanelProps("song-tabs", "cover", songTab === "cover")')
    cover_panel_end = page.index("</div>", cover_panel_start)
    assert 'ContentText contentKey="search_songs_note"' in page[cover_panel_start:cover_panel_end]


def test_search_steps_renumber_when_a_step_is_removed():
    """단계 하나를 지우면 STEP 1, STEP 3 처럼 번호가 비어 버린다."""
    grid = source("pages", "search", "StepGrid.jsx")
    assert "image.hidden" in grid
    assert "STEP {index + 1}" in grid


# --- 오프라인 이벤트 화면 ---------------------------------------------------

def test_offline_cards_do_not_nest_links_inside_a_button():
    """버튼 안의 링크는 표준에서 허용하지 않고 낭독기도 제대로 읽지 못한다."""
    page = source("pages", "OfflinePage.jsx")
    assert "event-card-main" in page
    assert "stopPropagation" not in page


def test_offline_card_text_starts_at_the_left_edge():
    """<button>은 안쪽 내용을 통째로 가운데로 모은다. text-align 만으로는 안 된다."""
    css = source("styles", "offline.css")
    main = css.split(".event-card-main {")[1].split("}")[0]
    assert "text-align: left" in main
    assert "justify-content: stretch" in main


def test_offline_explains_itself_when_the_map_is_missing():
    """빈 상자만 남으면 고장인지 아직 불러오는 중인지 알 수 없다."""
    page = source("pages", "OfflinePage.jsx")
    css = source("styles", "offline.css")
    assert "map-fallback" in page
    # 지도 인증이 막히면 스크립트는 멀쩡히 올라오고 화면만 빈다.
    assert "navermap_authFailure" in page
    assert ".map-fallback" in css


def test_offline_gives_the_map_a_box_of_its_own():
    """지도는 제 칸의 자식을 통째로 갈아치운다. 우리가 그린 것을 같이 두면 화면이 멈춘다."""
    page = source("pages", "OfflinePage.jsx")
    assert 'className="map-canvas"' in page
    assert ".map-canvas" in source("styles", "offline.css")


def test_offline_list_scrolls_on_its_own_only_beside_the_map():
    """좁은 화면에서 안쪽 스크롤을 두면 페이지를 내리려다 목록 안에 갇힌다."""
    css = source("styles", "offline.css")
    wide = css.split("@media (min-width: 900px)")[1]
    assert "overflow-y: auto" in wide
    assert css.split("@media (min-width: 900px)")[0].count("overflow-y: auto") == 0


# --- 배색과 좁은 화면 -------------------------------------------------------

def test_dark_theme_is_defined_for_the_whole_site(client):
    css = client.get("/assets/site.css").get_data(as_text=True)
    assert ':root[data-theme="dark"]' in css
    assert ".theme-toggle" in css


def test_the_app_reuses_the_shared_palette():
    """색은 한 곳에서만 정한다. 옮겨 적으면 관리자 화면과 공개 화면이 어긋난다."""
    assert "stelline/static/assets/site.css" in source("main.jsx")
    # React 전환에서 새로 넣은 CSS 는 움직임과 빈자리뿐이라, 색은 토큰으로만 쓴다.
    app_css = source("styles", "app.css")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", app_css)
    assert not re.search(r"\b(rgb|hsl)a?\(", app_css)


def test_header_stacks_the_brand_above_the_menu_on_narrow_screens(client):
    """한 줄에 같이 두면 이름이 폭의 절반을 먹고 메뉴가 세 줄까지 접혔다."""
    css = client.get("/assets/site.css").get_data(as_text=True)
    narrow = css.split("@media (max-width: 720px)")[-1]
    header = narrow.split(".site-header {")[1].split("}")[0]
    assert "flex-direction: column" in header


def test_a_main_panel_without_its_pair_takes_the_whole_row(client):
    """벅스 대상이 없으면 이벤트 칸이 왼쪽 절반에만 서서 제목이 여러 줄로 접히고 오른쪽 절반이 비었다."""
    css = client.get("/assets/site.css").get_data(as_text=True)
    wide = css.split("@media (min-width: 900px)")[1].split("@media")[0]
    assert ".info-stack.is-split > .section-panel:only-child" in wide
    assert ".info-stack.is-split > .is-full + .section-panel:last-child" in wide


def test_narrow_tabs_drop_the_count_before_breaking_the_name(client):
    """휴대폰 폭에서 세 탭이 한 줄에 안 들어가 '지금 / 막힘'처럼 이름 한가운데가 끊겼다."""
    css = client.get("/assets/site.css").get_data(as_text=True)
    narrow = css.split("@media (max-width: 720px)")[-1]
    tab = narrow.split(".section-actions > .segmented button {")[1].split("}")[0]
    assert "flex-wrap: wrap" in tab
    assert "word-break: keep-all" in tab


def test_karaoke_toolbar_does_not_spread_over_four_rows_on_phones():
    """화면 위에 붙어 다니는 칸이라, '필터'·'여러 곡'이 한 줄씩 차지하면 그만큼 목록이 가려진다."""
    narrow = source("styles", "karaoke.css").split("@media (max-width: 640px)")[1]
    assert ".kara-toolbar-end { display: contents; }" in narrow


def test_karaoke_symbol_buttons_have_names():
    """기호(☆·+)만 있는 단추는 낭독기가 '흰 별'처럼 기호 이름을 읽는다."""
    for parts in (("pages", "karaoke", "SongCard.jsx"), ("pages", "karaoke", "MultiPickDialog.jsx")):
        text = source(*parts)
        assert "aria-label={`${song.title} 즐겨찾기`}" in text
        assert "aria-label={`${song.title} 부를 곡 목록에 담기`}" in text
