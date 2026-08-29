"""관리자용 콘텐츠 관리 화면."""

from functools import wraps
import logging
import secrets

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, URLSafeSerializer

from stelline.config import ADMIN_HTML_SNAPSHOT_PATH, APP_ENV, SECRET_KEY
from stelline.database.connection import get_connection
from stelline.database.import_admin_html import import_snapshot, parse_snapshot
from stelline.database.migrate import apply_migrations

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# 운영자가 수정할 콘텐츠만 명시적으로 허용한다.
CONTENT_TABLES = {
    "events": {"title": "이벤트·펀딩", "description": "메인 화면에 표시할 외부 이벤트 링크입니다.", "fields": ("title", "link", "expires_at")},
    "twits": {"title": "트윗 안내", "description": "태그·키워드는 쉼표로 구분해 입력하세요.", "fields": ("title", "time", "tags", "keywords", "expires_at")},
    "targets": {"title": "Bugs 순위 대상", "description": "Bugs 즐겨찾기 페이지 번호를 입력하면 순위를 주기적으로 표시합니다.", "fields": ("name", "title", "url_number", "expires_at")},
    "offline": {"title": "오프라인 이벤트", "description": "주소를 입력하면 빈 지도 좌표가 자동으로 보완됩니다. 링크는 쉼표로 구분하세요.", "fields": ("name", "location_name", "address", "description", "start_date", "end_date", "latitude", "longitude", "always")},
    "song_infos": {"title": "검색 점검 곡", "description": "YouTube 검색 노출을 확인할 곡입니다. risk는 비워 두거나 0으로 입력하세요.", "fields": ("query", "video_id", "risk")},
}
READ_ONLY_TABLES = ("songs_data", "recent_data", "record_main", "record_search", "song_counts", "fcm_tokens")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    if "admin_csrf" not in session:
        session["admin_csrf"] = secrets.token_urlsafe(32)
    return session["admin_csrf"]


def require_csrf():
    if not secrets.compare_digest(request.form.get("csrf_token", ""), session.get("admin_csrf", "")):
        abort(400, "잘못된 요청입니다. 페이지를 새로고침한 뒤 다시 시도하세요.")


def row_serializer():
    return URLSafeSerializer(SECRET_KEY, salt="admin-row-delete")


def serialize_row(row):
    """DB의 datetime 등을 JSON으로 안전하게 서명해 삭제 폼에 전달한다."""
    return row_serializer().dumps({key: str(value) if value is not None else None for key, value in row.items()})


def input_type(field):
    if field in {"expires_at", "start_date", "end_date"}:
        return "datetime-local"
    if field in {"url_number", "risk", "latitude", "longitude"}:
        return "number"
    return "text"


def load_table(connection, table_name):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM `{table_name}`")
        return cursor.fetchall()


@admin_bp.route("/")
@login_required
def admin_index():
    data, connection = {}, None
    try:
        connection = get_connection()
        for table_name in (*CONTENT_TABLES, *READ_ONLY_TABLES):
            data[table_name] = load_table(connection, table_name)
    except Exception:
        logging.exception("관리자 데이터를 불러오지 못했습니다.")
        flash("일부 데이터를 불러오지 못했습니다. DB 연결과 테이블 구성을 확인하세요.", "error")
    finally:
        if connection:
            connection.close()
    forms = {name: {**definition, "inputs": [{"name": field, "type": input_type(field)} for field in definition["fields"]]} for name, definition in CONTENT_TABLES.items()}
    return render_template(
        "admin/index.html",
        data=data,
        forms=forms,
        csrf_token=csrf_token(),
        serialize_row=serialize_row,
        development_mode=APP_ENV == "development",
    )


@admin_bp.route("/dev/import-snapshot", methods=["POST"])
@login_required
def import_snapshot_from_admin_html():
    require_csrf()
    if APP_ENV != "development":
        abort(403, "개발 환경에서만 사용할 수 있습니다.")
    if not ADMIN_HTML_SNAPSHOT_PATH:
        flash("개발용 관리자 HTML 경로가 설정되지 않았습니다. ADMIN_HTML_SNAPSHOT_PATH를 확인하세요.", "error")
        return redirect(url_for("admin.admin_index"))

    try:
        # Ensure schema migrations are applied (so primary key change runs)
        apply_migrations()
        snapshot = parse_snapshot(ADMIN_HTML_SNAPSHOT_PATH)
        import_snapshot(snapshot, replace=True)
        flash("개발 DB를 관리자 HTML 스냅샷으로 다시 적재했습니다.", "success")
    except Exception:
        logging.exception("개발용 관리자 HTML 스냅샷 적재 실패")
        flash("스냅샷 파일을 읽거나 적재하지 못했습니다. 경로와 파일 내용을 확인하세요.", "error")
    return redirect(url_for("admin.admin_index"))


@admin_bp.route("/data/<table_name>", methods=["POST"])
@login_required
def add_row(table_name):
    require_csrf()
    definition = CONTENT_TABLES.get(table_name)
    if definition is None:
        abort(404)
    fields = definition["fields"]
    values = [request.form.get(field, "").strip() or None for field in fields]
    if not any(value is not None for value in values):
        flash("저장할 내용을 입력하세요.", "error")
        return redirect(url_for("admin.admin_index"))

    connection = None
    try:
        connection = get_connection()
        columns = ", ".join(f"`{field}`" for field in fields)
        with connection.cursor() as cursor:
            cursor.execute(f"INSERT INTO `{table_name}` ({columns}) VALUES ({', '.join(['%s'] * len(fields))})", values)
        connection.commit()
        flash(f"{definition['title']} 항목을 추가했습니다.", "success")
    except Exception:
        logging.exception("관리자 데이터 추가 실패: %s", table_name)
        if connection:
            connection.rollback()
        flash("저장하지 못했습니다. 필수 항목과 데이터 형식을 확인하세요.", "error")
    finally:
        if connection:
            connection.close()
    return redirect(url_for("admin.admin_index"))


@admin_bp.route("/data/<table_name>/delete", methods=["POST"])
@login_required
def delete_row(table_name):
    require_csrf()
    if table_name not in CONTENT_TABLES:
        abort(404)
    try:
        row = row_serializer().loads(request.form["row_token"])
    except (KeyError, BadSignature):
        abort(400, "삭제 요청이 만료되었거나 잘못되었습니다.")
    allowed_columns = set(CONTENT_TABLES[table_name]["fields"])
    conditions = [(key, value) for key, value in row.items() if key in allowed_columns]
    if not conditions:
        abort(400)

    connection = None
    try:
        connection = get_connection()
        where = " AND ".join(f"`{key}` <=> %s" for key, _ in conditions)
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM `{table_name}` WHERE {where}", [value for _, value in conditions])
        connection.commit()
        flash("항목을 삭제했습니다.", "success")
    except Exception:
        logging.exception("관리자 데이터 삭제 실패: %s", table_name)
        if connection:
            connection.rollback()
        flash("삭제하지 못했습니다.", "error")
    finally:
        if connection:
            connection.close()
    return redirect(url_for("admin.admin_index"))
