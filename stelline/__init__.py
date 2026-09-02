"""Flask 애플리케이션 초기화와 라우트 등록."""

import logging
from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS

from stelline.admin import admin_bp
from stelline.apis import api_bp
from stelline.auth import auth_bp
from stelline.background_tasks import start_background_tasks
from stelline.config import AUTO_CREATE_SCHEMA, SECRET_KEY, START_BACKGROUND_TASKS
from stelline.database.migrate import apply_migrations
from stelline.logging_config import setup_logging

setup_logging()

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = SECRET_KEY
# 관리자 화면의 그림 올리기가 유일한 파일 업로드다. 항목별 상한은 이보다 훨씬 작지만,
# 그보다 큰 요청은 본문을 읽기도 전에 끊어 메모리를 붙들지 않게 한다.
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
CORS(app)


@app.errorhandler(413)
def payload_too_large(error):
    return "올린 파일이 너무 큽니다. 관리자 화면에 적힌 용량 상한을 지켜 주세요.", 413

# 화면 경로는 고정이라 요청마다 다시 조립할 이유가 없다.
STATIC_ROOT = Path(app.static_folder)

# 공개 화면은 React 한 벌(SPA)이다. 어느 주소로 들어와도 같은 문서를 내려주고,
# 그 안에서 화면을 고르는 일은 브라우저가 한다. 주소 자체는 예전 그대로라서
# 링크를 그대로 눌러도, 새로 고쳐도, 뒤로 가기를 해도 같은 화면이 나온다.
#
# 목록은 여기 한 곳에만 적는다. 화면을 늘릴 때 라우트를 따로 만들지 않아도 되고,
# 빠뜨려서 어떤 주소만 404가 되는 일도 없다.
PAGE_ROUTES = ("search", "congratulation", "offline", "karaoke")


def send_app_shell():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/")
def index():
    return send_app_shell()


for _name in PAGE_ROUTES:
    # 끝의 빗금이 있든 없든 같은 문서를 내려준다(예전 동작 그대로다).
    app.add_url_rule(f"/{_name}", endpoint=f"{_name}_page", view_func=send_app_shell)
    app.add_url_rule(f"/{_name}/", endpoint=f"{_name}_page_slash", view_func=send_app_shell)

app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(auth_bp, url_prefix="/auth")


@app.route("/<path:filename>")
def serve_static(filename):
    """파비콘·안내 그림·빌드 결과물처럼 실제로 있는 파일만 내려준다.

    없는 주소는 그대로 404다. 화면 주소는 위에서 이미 다 잡아 두었으므로,
    여기서 SPA 문서를 대신 내려주면 오타 난 주소까지 200으로 답하게 된다.
    """
    target = STATIC_ROOT / filename
    if target.is_file():
        return send_from_directory(str(STATIC_ROOT), filename)
    return "Not Found", 404


if AUTO_CREATE_SCHEMA:
    apply_migrations()

# 개발에서는 기본적으로 꺼 두어 외부 API와 운영 알림을 건드리지 않는다.
if START_BACKGROUND_TASKS:
    start_background_tasks()
logging.info("Flask 앱 초기화 완료.")
