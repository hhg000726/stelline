"""관리자용 콘텐츠 관리 화면."""

from functools import wraps
import logging
import secrets

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, URLSafeSerializer

from stelline.config import ADMIN_HTML_SNAPSHOT_PATH, APP_ENV, SECRET_KEY
from stelline.database.connection import get_connection
from stelline.database.import_admin_html import import_snapshot, parse_snapshot
from stelline.database.karaoke_release_dates import extract_video_id
from stelline.database.karaoke_seed import SeedError, import_seed_file, import_text
from stelline.database.migrate import apply_migrations

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# 운영자가 수정할 콘텐츠만 명시적으로 허용한다.
CONTENT_TABLES = {
    "events": {"title": "이벤트·펀딩", "description": "메인 화면에 표시할 외부 이벤트 링크입니다.", "fields": ("title", "link", "expires_at")},
    "twits": {"title": "트윗 안내", "description": "태그·키워드는 쉼표로 구분해 입력하세요.", "fields": ("title", "time", "tags", "keywords", "expires_at")},
    "targets": {"title": "Bugs 순위 대상", "description": "Bugs 즐겨찾기 페이지 번호를 입력하면 순위를 주기적으로 표시합니다.", "fields": ("name", "title", "url_number", "expires_at")},
    "offline": {"title": "오프라인 이벤트", "description": "주소를 입력하면 빈 지도 좌표가 자동으로 보완됩니다. 링크는 쉼표로 구분하세요.", "fields": ("name", "location_name", "address", "description", "start_date", "end_date", "latitude", "longitude", "always")},
    "song_infos": {"title": "검색 점검 곡", "description": "YouTube 검색 노출을 확인할 곡입니다. risk는 비워 두거나 0으로 입력하세요.", "fields": ("query", "video_id", "risk")},
    "song_reports": {"title": "누락 노래 제보", "description": "사용자가 검색 목록에 없다고 제보한 내용을 확인하고 삭제합니다.", "fields": ("content",), "key_fields": ("id",)},
    "view_reports": {"title": "조회수 알림 누락 제보", "description": "사용자가 조회수 알림에서 누락되었다고 제보한 내용을 확인하고 삭제합니다.", "fields": ("content",), "key_fields": ("id",)},
    "karaoke_songs": {
        "title": "노래방 번호",
        "description": "노래방 번호 페이지에 표시할 곡입니다. 번호가 없으면 비워 두고, 멤버는 쉼표로 구분하세요. 순서는 작을수록 위(최신)에 옵니다."
                       " 유튜브 영상을 적어 두면 비어 있는 발매일을 업로드 날짜로 한 번에 채울 수 있습니다.",
        "fields": ("title", "artist", "tj", "ky", "section", "category", "members", "release_date", "youtube_video_id", "title_alt", "note", "sort_order"),
        "labels": {
            "title": "곡명", "artist": "가수(표시용)", "tj": "TJ 번호", "ky": "금영 번호",
            "section": "구분", "category": "종류", "members": "참여 멤버(쉼표 구분)", "release_date": "발매일",
            "youtube_video_id": "유튜브 영상(주소 또는 ID)",
            "title_alt": "검색용 다른 표기", "note": "비고", "sort_order": "정렬 순서",
        },
        "key_fields": ("id",),
        "bulk_import": True,
        "searchable": True,
        # 곡이 수백 개라 목록을 넓게 펴고, 표에는 눈으로 훑을 열만 남긴다.
        # 나머지 값은 행을 클릭하면 수정 양식에 그대로 채워진다.
        "wide": True,
        "list_fields": ("title", "artist", "section", "category", "tj", "ky", "release_date", "youtube_video_id", "members"),
        # 표 머리글은 양식보다 짧아야 열이 좁아지지 않는다.
        "list_labels": {"artist": "가수", "tj": "TJ", "ky": "금영", "youtube_video_id": "유튜브", "members": "참여 멤버"},
    },
    "karaoke_members": {"title": "노래방 멤버 목록", "description": "노래방 페이지 멤버 필터의 순서와 유닛 묶음입니다. 졸업일을 넣으면 필터에서 졸업으로 묶이고, 유닛을 옮긴 멤버는 이전 유닛에 적어 두세요.", "fields": ("name", "unit", "former_units", "debut_date", "graduated_at", "display_order"), "labels": {"name": "멤버 이름", "unit": "현재 소속 유닛", "former_units": "이전 유닛(쉼표 구분)", "debut_date": "데뷔일", "graduated_at": "졸업일", "display_order": "표시 순서"}},
    "karaoke_reports": {"title": "노래방 번호 제보", "description": "사용자가 남긴 노래방 번호 추가·정정 제보입니다.", "fields": ("content",), "key_fields": ("id",)},
    "main_buttons": {
        "title": "메인 화면 버튼",
        "description": "메인 화면 상단 버튼을 감추거나 다시 보이게 합니다. 표시 순서는 작을수록 왼쪽에 옵니다. 버튼 키는 화면에 심어 둔 값이라 바꾸지 마세요.",
        "fields": ("button_key", "label", "visible", "display_order"),
        "labels": {"button_key": "버튼 키(수정 금지)", "label": "버튼 이름", "visible": "표시 여부", "display_order": "표시 순서"},
        "key_fields": ("button_key",),
    },
}
READ_ONLY_TABLES = ("songs_data", "recent_data", "record_main", "record_search", "record_karaoke", "song_counts", "fcm_tokens")

# 붙여 넣은 유튜브 주소는 영상 ID만 남겨 저장한다. 알아볼 수 없으면 입력한 값을 그대로 두어
# 잘못 넣었다는 사실이 화면에 드러나게 한다.
FIELD_NORMALIZERS = {
    "youtube_video_id": lambda value: extract_video_id(value) or value,
}

# 값이 정해져 있는 열은 직접 입력 대신 선택 목록으로 보여준다.
FIELD_CHOICES = {
    "section": (("group", "단체"), ("unit", "유닛"), ("collab", "콜라보"), ("gift", "기프트"), ("solo", "개인")),
    "category": (("original", "오리지널"), ("cover", "커버")),
    "visible": (("1", "표시"), ("0", "숨김")),
}


def normalize_field(field, value):
    """저장 전에 다듬어야 하는 열의 값을 손본다."""
    normalizer = FIELD_NORMALIZERS.get(field)
    return normalizer(value) if normalizer else value


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
    """DB의 datetime 등을 JSON으로 안전하게 서명해 수정·삭제 폼에 전달한다."""
    return row_serializer().dumps({key: str(value) if value is not None else None for key, value in row.items()})


def load_row_token(token):
    """서명된 행 토큰을 되돌린다. 위조·만료된 토큰은 400으로 막는다."""
    try:
        return row_serializer().loads(token)
    except (TypeError, BadSignature):
        abort(400, "요청이 만료되었거나 잘못되었습니다. 페이지를 새로고침한 뒤 다시 시도하세요.")


def input_type(field):
    if field in {"expires_at", "start_date", "end_date"}:
        return "datetime-local"
    if field in {"release_date", "debut_date", "graduated_at"}:
        return "date"
    if field in {"url_number", "risk", "latitude", "longitude", "sort_order", "display_order"}:
        return "number"
    return "text"


def load_table(connection, table_name):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM `{table_name}`")
        return cursor.fetchall()


def nullable_columns(connection, table_name):
    """비워 두면 NULL로 저장해도 되는 열 이름을 모은다.

    NOT NULL 열은 빈 칸으로 지울 수 없으므로 수정 시 기존 값을 유지한다.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COLUMN_NAME, IS_NULLABLE FROM information_schema.COLUMNS"
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            (table_name,),
        )
        return {row["COLUMN_NAME"] for row in cursor.fetchall() if row["IS_NULLABLE"] == "YES"}


def row_conditions(definition, row):
    """수정·삭제 대상 행을 특정하는 WHERE 조건을 만든다."""
    allowed_columns = set(definition.get("key_fields", definition["fields"]))
    return [(key, value) for key, value in row.items() if key in allowed_columns]


@admin_bp.route("/")
@login_required
def admin_index():
    data, connection = {}, None
    missing_tables = []
    try:
        connection = get_connection()
        for table_name in (*CONTENT_TABLES, *READ_ONLY_TABLES):
            try:
                data[table_name] = load_table(connection, table_name)
            except Exception:
                logging.exception("관리자 테이블 로드 실패: %s", table_name)
                missing_tables.append(table_name)
    except Exception:
        logging.exception("관리자 DB 연결 실패")
        flash("DB 연결을 확인할 수 없습니다. 데이터베이스 상태와 접근 계정을 확인하세요.", "error")
    else:
        if missing_tables:
            flash("일부 테이블을 불러오지 못했습니다. DB 연결과 테이블 구성을 확인하세요.", "error")
    finally:
        if connection:
            connection.close()
    forms = {
        name: {
            **definition,
            # 표 머리글도 양식과 같은 한글 이름을 쓴다. 목록에 보일 열을 따로 정하지
            # 않은 테이블은 지금처럼 모든 열을 그대로 보여준다.
            "columns": [
                {
                    "name": field,
                    "label": definition.get("list_labels", {}).get(field)
                             or definition.get("labels", {}).get(field, field),
                    # 구분·종류처럼 값이 정해진 열은 표에서도 한글 이름으로 보여준다.
                    "choices": dict(FIELD_CHOICES.get(field, ())),
                }
                for field in definition.get("list_fields", ())
            ],
            "inputs": [
                {
                    "name": field,
                    # 표시 이름을 따로 정하지 않은 테이블은 기존처럼 열 이름을 그대로 보여준다.
                    "label": definition.get("labels", {}).get(field, field),
                    "type": input_type(field),
                    "choices": FIELD_CHOICES.get(field),
                }
                for field in definition["fields"]
            ],
        }
        for name, definition in CONTENT_TABLES.items()
    }
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
    # 빈 칸은 INSERT 대상에서 빼서 열의 기본값이 그대로 쓰이게 한다.
    entries = [(field, normalize_field(field, value)) for field in definition["fields"] if (value := request.form.get(field, "").strip())]
    if not entries:
        flash("저장할 내용을 입력하세요.", "error")
        return redirect(url_for("admin.admin_index"))

    connection = None
    try:
        connection = get_connection()
        columns = ", ".join(f"`{field}`" for field, _ in entries)
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO `{table_name}` ({columns}) VALUES ({', '.join(['%s'] * len(entries))})",
                [value for _, value in entries],
            )
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


@admin_bp.route("/data/<table_name>/update", methods=["POST"])
@login_required
def update_row(table_name):
    """표에서 고른 행을 같은 양식으로 수정한다.

    대상 행은 서명된 `row_token`으로만 지정할 수 있어 임의의 행을 건드릴 수 없다.
    """
    require_csrf()
    definition = CONTENT_TABLES.get(table_name)
    if definition is None:
        abort(404)
    row = load_row_token(request.form.get("row_token", ""))
    conditions = row_conditions(definition, row)
    if not conditions:
        abort(400, "수정할 행을 특정할 수 없습니다.")

    connection = None
    try:
        connection = get_connection()
        nullable = nullable_columns(connection, table_name)
        # 빈 칸은 값을 지우겠다는 뜻이지만, NOT NULL 열은 지울 수 없어 기존 값을 유지한다.
        assignments = []
        for field in definition["fields"]:
            value = request.form.get(field, "").strip()
            if value:
                assignments.append((field, normalize_field(field, value)))
            elif field in nullable:
                assignments.append((field, None))
        if not assignments:
            flash("수정할 내용을 입력하세요.", "error")
            return redirect(url_for("admin.admin_index"))

        setters = ", ".join(f"`{field}` = %s" for field, _ in assignments)
        where = " AND ".join(f"`{key}` <=> %s" for key, _ in conditions)
        condition_values = [value for _, value in conditions]
        with connection.cursor() as cursor:
            # 값이 그대로면 UPDATE의 반영 행 수가 0이므로, 대상 존재 여부는 따로 확인한다.
            cursor.execute(f"SELECT COUNT(*) AS matched FROM `{table_name}` WHERE {where}", condition_values)
            if not cursor.fetchone()["matched"]:
                flash("수정할 항목을 찾지 못했습니다. 목록을 새로고침한 뒤 다시 시도하세요.", "error")
                return redirect(url_for("admin.admin_index"))
            cursor.execute(
                f"UPDATE `{table_name}` SET {setters} WHERE {where}",
                [value for _, value in assignments] + condition_values,
            )
        connection.commit()
        flash(f"{definition['title']} 항목을 수정했습니다.", "success")
    except Exception:
        logging.exception("관리자 데이터 수정 실패: %s", table_name)
        if connection:
            connection.rollback()
        flash("수정하지 못했습니다. 값의 형식과 중복 여부를 확인하세요.", "error")
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
    definition = CONTENT_TABLES[table_name]
    row = load_row_token(request.form.get("row_token", ""))
    conditions = row_conditions(definition, row)
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


@admin_bp.route("/karaoke/import", methods=["POST"])
@login_required
def import_karaoke_songs():
    """노래방 곡을 한 번에 여러 개 등록한다.

    `source=seed`는 저장소에 들어 있는 기본 목록을, 그 밖에는 붙여넣은 표를 사용한다.
    곡명과 가수가 같으면 새로 만들지 않고 기존 곡을 갱신한다.
    """
    require_csrf()
    replace = request.form.get("replace") == "on"
    try:
        if request.form.get("source") == "seed":
            stats = import_seed_file(replace=replace)
        else:
            stats = import_text(request.form.get("bulk_text", ""), replace=replace)
    except SeedError as error:
        flash(str(error), "error")
    except Exception:
        logging.exception("노래방 곡 일괄 등록 실패")
        flash("일괄 등록에 실패했습니다. 입력 형식과 DB 상태를 확인하세요.", "error")
    else:
        for warning in stats["warnings"][:5]:
            flash(warning, "error")
        flash(
            f"노래방 곡 {stats['total']}건을 처리했습니다. (새로 추가 {stats['inserted']}건, 갱신 {stats['updated']}건"
            + (", 기존 곡 전체 삭제 후 등록)" if stats["replaced"] else ")"),
            "success",
        )
    return redirect(url_for("admin.admin_index"))
