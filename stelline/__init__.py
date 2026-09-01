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
CORS(app)

# 화면 경로는 고정이라 요청마다 다시 조립할 이유가 없다.
STATIC_ROOT = Path(app.static_folder)
PAGE_DIRS = {name: str(STATIC_ROOT / name) for name in ("search", "congratulation", "offline", "karaoke")}


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/search")
@app.route("/search/")
def search_page():
    return send_from_directory(PAGE_DIRS["search"], "index.html")


@app.route("/congratulation")
@app.route("/congratulation/")
def congratulation_page():
    return send_from_directory(PAGE_DIRS["congratulation"], "index.html")


@app.route("/offline")
@app.route("/offline/")
def offline_page():
    return send_from_directory(PAGE_DIRS["offline"], "index.html")


@app.route("/karaoke")
@app.route("/karaoke/")
def karaoke_page():
    return send_from_directory(PAGE_DIRS["karaoke"], "index.html")

app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(auth_bp, url_prefix="/auth")


@app.route("/<path:filename>")
def serve_static(filename):
    target = STATIC_ROOT / filename
    # 디렉터리 검사를 먼저 한다. 뒤에 두면 exists()에서 이미 걸려 index.html을
    # 내려 줄 기회가 사라진다(디렉터리는 파일이 아니라 그대로 404가 된다).
    if target.is_dir() and (target / "index.html").exists():
        return send_from_directory(str(target), "index.html")
    if target.exists():
        return send_from_directory(str(STATIC_ROOT), filename)
    return "Not Found", 404


if AUTO_CREATE_SCHEMA:
    apply_migrations()

# 개발에서는 기본적으로 꺼 두어 외부 API와 운영 알림을 건드리지 않는다.
if START_BACKGROUND_TASKS:
    start_background_tasks()
logging.info("Flask 앱 초기화 완료.")
