"""Flask 애플리케이션 초기화와 라우트 등록."""

import logging
from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS

from stelline.admin import admin_bp
from stelline.apis import api_bp
from stelline.auth import auth_bp
from stelline.background_tasks.runner import start_background_tasks
from stelline.config import AUTO_CREATE_SCHEMA, SECRET_KEY, START_BACKGROUND_TASKS
from stelline.database.migrate import apply_migrations
from stelline.logging_config import setup_logging

setup_logging()

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = SECRET_KEY
CORS(app)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/search")
@app.route("/search/")
def search_page():
    return send_from_directory(str(Path(app.static_folder) / "search"), "index.html")


@app.route("/congratulation")
@app.route("/congratulation/")
def congratulation_page():
    return send_from_directory(str(Path(app.static_folder) / "congratulation"), "index.html")


@app.route("/offline")
@app.route("/offline/")
def offline_page():
    return send_from_directory(str(Path(app.static_folder) / "offline"), "index.html")
app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(auth_bp, url_prefix="/auth")


@app.route("/<path:filename>")
def serve_static(filename):
    base = Path(app.static_folder)
    target = base / filename
    if target.exists():
        return send_from_directory(str(base), filename)
    if target.is_dir():
        index_path = target / "index.html"
        if index_path.exists():
            return send_from_directory(str(target), "index.html")
    return "Not Found", 404


if AUTO_CREATE_SCHEMA:
    apply_migrations()

# 개발에서는 기본적으로 꺼 두어 외부 API와 운영 알림을 건드리지 않는다.
if START_BACKGROUND_TASKS:
    start_background_tasks()
logging.info("Flask 앱 초기화 완료.")
