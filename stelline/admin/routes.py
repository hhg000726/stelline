"""관리자용 콘텐츠 관리 화면."""

from functools import lru_cache, wraps
import logging
import secrets

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, URLSafeSerializer

from stelline.config import ADMIN_HTML_SNAPSHOT_PATH, APP_ENV, SECRET_KEY
from stelline.content import CONTENT_GROUPS, admin_rows
from stelline.database.connection import get_connection
from stelline.database.import_admin_html import import_snapshot, parse_snapshot
from stelline.database.karaoke_seed import SeedError, import_seed_file, import_text
from stelline.database.migrate import apply_migrations

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# 운영자가 수정할 콘텐츠만 명시적으로 허용한다.
#
# 화면은 표를 `group` 별로 묶어 한 번에 한 묶음만 보여준다. 한 화면에 열한 개의
# 표를 동시에 펼치면 무엇을 고쳐야 하는지 찾는 데만 시간이 걸린다.
CONTENT_TABLES = {
    "events": {
        "title": "이벤트·펀딩",
        "group": "main",
        "description": "메인 화면에 표시할 외부 이벤트 링크입니다.",
        "fields": ("title", "link", "expires_at"),
        "labels": {"title": "제목", "link": "링크", "expires_at": "만료 시각(비우면 계속 표시)"},
        "list_fields": ("title", "link", "expires_at"),
        "list_labels": {"expires_at": "만료 시각"},
    },
    "twits": {
        "title": "트윗 안내",
        "group": "main",
        "description": "태그·키워드는 쉼표로 구분해 입력하세요.",
        "fields": ("title", "time", "tags", "keywords", "expires_at"),
        "labels": {"title": "제목", "time": "시간 안내", "tags": "태그(쉼표 구분)", "keywords": "키워드(쉼표 구분)", "expires_at": "만료 시각(비우면 계속 표시)"},
        "list_fields": ("title", "time", "tags", "keywords", "expires_at"),
        "list_labels": {"tags": "태그", "keywords": "키워드", "expires_at": "만료 시각"},
    },
    "targets": {
        "title": "Bugs 순위 대상",
        "group": "main",
        "description": "Bugs 즐겨찾기 페이지 번호를 입력하면 순위를 주기적으로 표시합니다.",
        "fields": ("name", "title", "url_number", "expires_at"),
        "labels": {"name": "대상 이름", "title": "투표 제목", "url_number": "Bugs 페이지 번호", "expires_at": "만료 시각(비우면 계속 표시)"},
        "list_fields": ("name", "title", "url_number", "expires_at"),
        "list_labels": {"url_number": "페이지 번호", "expires_at": "만료 시각"},
    },
    "main_buttons": {
        "title": "메인 화면 버튼",
        "group": "main",
        "description": "메인 화면 기능 버튼을 감추거나 다시 보이게 합니다. 표시 순서는 작을수록 앞에 옵니다. 버튼 키는 화면에 심어 둔 값이라 바꾸지 마세요.",
        "fields": ("button_key", "label", "visible", "display_order"),
        "labels": {"button_key": "버튼 키(수정 금지)", "label": "버튼 이름", "visible": "표시 여부", "display_order": "표시 순서(비우면 맨 뒤)"},
        "list_fields": ("button_key", "label", "visible", "display_order"),
        "list_labels": {"button_key": "버튼 키", "label": "버튼 이름", "visible": "표시", "display_order": "순서"},
        "key_fields": ("button_key",),
        "order_field": "display_order",
    },
    "karaoke_songs": {
        "title": "노래방 번호",
        "group": "karaoke",
        "description": "노래방 번호 페이지에 표시할 곡입니다. 번호가 없으면 비워 두고, 멤버는 쉼표로 구분하세요. 목록은 화면에서 랜덤·가나다순으로 보여 주므로 순서를 정할 필요가 없습니다.",
        "fields": ("title", "artist", "tj", "ky", "section", "category", "members", "title_alt"),
        "labels": {
            "title": "곡명", "artist": "가수(표시용)", "tj": "TJ 번호", "ky": "금영 번호",
            "section": "구분", "category": "종류", "members": "참여 멤버(쉼표 구분)",
            "title_alt": "검색용 다른 표기",
        },
        "key_fields": ("id",),
        "bulk_import": True,
        "searchable": True,
        # 곡이 수백 개라 표에는 눈으로 훑을 열만 남긴다.
        # 나머지 값은 행을 클릭하면 수정 양식에 그대로 채워진다.
        "wide": True,
        "list_fields": ("title", "artist", "section", "category", "tj", "ky", "members"),
        # 표 머리글은 양식보다 짧아야 열이 좁아지지 않는다.
        "list_labels": {"artist": "가수", "tj": "TJ", "ky": "금영", "members": "참여 멤버"},
    },
    "karaoke_members": {
        "title": "노래방 멤버 목록",
        "group": "karaoke",
        "description": "노래방 페이지 멤버 필터의 순서와 유닛 묶음입니다. 졸업일을 넣으면 필터에서 졸업으로 묶이고, 유닛을 옮긴 멤버는 이전 유닛에 적어 두세요.",
        "fields": ("name", "unit", "former_units", "debut_date", "graduated_at", "display_order"),
        "labels": {"name": "멤버 이름", "unit": "현재 소속 유닛", "former_units": "이전 유닛(쉼표 구분)", "debut_date": "데뷔일", "graduated_at": "졸업일", "display_order": "표시 순서(비우면 맨 뒤)"},
        "list_fields": ("name", "unit", "former_units", "debut_date", "graduated_at", "display_order"),
        "list_labels": {"name": "이름", "unit": "유닛", "former_units": "이전 유닛", "debut_date": "데뷔일", "graduated_at": "졸업일", "display_order": "순서"},
        "order_field": "display_order",
    },
    "song_infos": {
        "title": "검색 점검 곡",
        "group": "search",
        "description": "YouTube 검색 노출을 확인할 곡입니다. 위험도는 비워 두거나 0으로 입력하세요.",
        "fields": ("query", "video_id", "risk"),
        "labels": {"query": "검색어", "video_id": "영상 ID", "risk": "위험도"},
        "list_fields": ("query", "video_id", "risk"),
        "searchable": True,
    },
    "offline": {
        "title": "오프라인 이벤트",
        "group": "offline",
        "description": "주소를 입력하면 빈 지도 좌표가 자동으로 보완됩니다. 관련 링크는 쉼표로 구분하세요.",
        "fields": ("name", "location_name", "address", "description", "start_date", "end_date", "latitude", "longitude", "always"),
        "labels": {
            "name": "행사 이름", "location_name": "장소 이름", "address": "주소",
            "description": "관련 링크(쉼표 구분)", "start_date": "시작", "end_date": "종료",
            "latitude": "위도", "longitude": "경도", "always": "상시 여부",
        },
        "list_fields": ("name", "location_name", "start_date", "end_date", "always"),
        "list_labels": {"name": "행사", "location_name": "장소", "always": "상시"},
    },
    "song_reports": {
        "title": "누락 노래 제보",
        "group": "reports",
        "description": "사용자가 검색 목록에 없다고 제보한 내용입니다.",
        "fields": ("content",),
        "labels": {"content": "제보 내용"},
        "list_fields": ("created_at", "content"),
        "list_labels": {"created_at": "받은 시각", "content": "제보 내용"},
        "key_fields": ("id",),
        # 제보는 사용자가 보내는 것이라, 관리자가 직접 넣을 일이 거의 없다.
        "collapse_form": True,
    },
    "view_reports": {
        "title": "조회수 알림 누락 제보",
        "group": "reports",
        "description": "사용자가 조회수 알림에서 누락되었다고 제보한 내용입니다.",
        "fields": ("content",),
        "labels": {"content": "제보 내용"},
        "list_fields": ("created_at", "content"),
        "list_labels": {"created_at": "받은 시각", "content": "제보 내용"},
        "key_fields": ("id",),
        "collapse_form": True,
    },
    "karaoke_reports": {
        "title": "노래방 번호 제보",
        "group": "reports",
        "description": "사용자가 남긴 노래방 번호 추가·정정 제보입니다.",
        "fields": ("content",),
        "labels": {"content": "제보 내용"},
        "list_fields": ("created_at", "content"),
        "list_labels": {"created_at": "받은 시각", "content": "제보 내용"},
        "key_fields": ("id",),
        "collapse_form": True,
    },
}

# 화면 위쪽 탭. 순서가 곧 탭 순서다.
TABLE_GROUPS = (
    ("main", "메인 화면"),
    ("karaoke", "노래방"),
    ("search", "검색 점검"),
    ("offline", "오프라인"),
    ("reports", "사용자 제보"),
)

READ_ONLY_TABLES = ("songs_data", "recent_data", "record_main", "record_search", "record_karaoke", "song_counts", "fcm_tokens")

# 값이 정해져 있는 열은 직접 입력 대신 선택 목록으로 보여준다.
FIELD_CHOICES = {
    "section": (("group", "단체"), ("unit", "유닛"), ("collab", "콜라보"), ("gift", "기프트"), ("solo", "개인")),
    "category": (("original", "오리지널"), ("cover", "커버")),
    "visible": (("1", "표시"), ("0", "숨김")),
    "always": (("0", "기간 있음"), ("1", "상시")),
}


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


@lru_cache(maxsize=1)
def row_serializer():
    """서명 객체는 상태가 없고 스레드 안전하므로 한 번만 만들어 재사용한다.

    (행마다 새로 만들면 표 하나를 그리는 데 수백 개를 만들었다 버리게 된다.)
    """
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


def _build_forms():
    """CONTENT_TABLES 로부터 화면이 쓰는 폼 구조를 만든다.

    입력값이 모두 모듈 상수라 요청마다 다시 만들 이유가 없어 import 시 한 번만 계산한다.
    """
    return {
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


FORMS = _build_forms()

# 표를 묶음별로 나눠 화면에서 탭으로 전환한다. 비어 있는 탭은 만들지 않는다.
TABLE_GROUP_VIEWS = [
    group
    for group in (
        {
            "key": key,
            "label": label,
            "forms": {name: form for name, form in FORMS.items() if form.get("group") == key},
        }
        for key, label in TABLE_GROUPS
    )
    if group["forms"]
]


def load_table(connection, table_name):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM `{table_name}`")
        return cursor.fetchall()


def nullable_columns(cursor, table_name):
    """비워 두면 NULL로 저장해도 되는 열 이름을 모은다.

    NOT NULL 열은 빈 칸으로 지울 수 없으므로 수정 시 기존 값을 유지한다.
    """
    cursor.execute(
        "SELECT COLUMN_NAME, IS_NULLABLE FROM information_schema.COLUMNS"
        " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        (table_name,),
    )
    return {row["COLUMN_NAME"] for row in cursor.fetchall() if row["IS_NULLABLE"] == "YES"}


def content_table(table_name):
    """관리자가 고칠 수 있는 표만 통과시킨다."""
    definition = CONTENT_TABLES.get(table_name)
    if definition is None:
        abort(404)
    return definition


def target_conditions(definition, token):
    """서명된 행 토큰에서 수정·삭제 대상을 특정하는 WHERE 조건을 만든다."""
    row = load_row_token(token)
    allowed_columns = set(definition.get("key_fields", definition["fields"]))
    return [(key, value) for key, value in row.items() if key in allowed_columns]


def where_clause(conditions):
    return " AND ".join(f"`{key}` <=> %s" for key, _ in conditions), [value for _, value in conditions]


def apply_write(table_name, log_label, failure_message, write):
    """관리자 쓰기 작업 하나를 실행하고 결과를 알린다.

    `write(cursor)`는 사용자에게 보여 줄 (문구, 종류)를 돌려준다. 어디서 실패하든
    롤백하고 같은 안내를 띄우므로, 라우트마다 뒷정리를 다시 적지 않는다.
    """
    connection = None
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            message = write(cursor)
        connection.commit()
    except Exception:
        logging.exception("%s: %s", log_label, table_name)
        if connection is not None:
            connection.rollback()
        message = (failure_message, "error")
    finally:
        if connection is not None:
            connection.close()
    flash(*message)
    return redirect(url_for("admin.admin_index"))


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
    # 표 묶음별 항목 수만 요청마다 달라진다. 나머지 폼 구조는 상수에서 미리 만들어 둔다.
    groups = [
        {**group, "count": sum(len(data.get(name, [])) for name in group["forms"])}
        for group in TABLE_GROUP_VIEWS
    ]
    return render_template(
        "admin/index.html",
        data=data,
        forms=FORMS,
        groups=groups,
        # 문구·그림은 표가 아니라 항목 단위로 고친다. 값은 DB가 비어 있어도 기본값으로 채워진다.
        content_groups=CONTENT_GROUPS,
        content_rows=admin_rows(),
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
    definition = content_table(table_name)
    # 빈 칸은 INSERT 대상에서 빼서 열의 기본값이 그대로 쓰이게 한다.
    entries = [(field, value) for field in definition["fields"] if (value := request.form.get(field, "").strip())]
    if not entries:
        flash("저장할 내용을 입력하세요.", "error")
        return redirect(url_for("admin.admin_index"))

    def write(cursor):
        # 순서 열을 비워 두면 열의 기본값(0)이 들어가 목록 맨 앞에 끼어든다. 맨 뒤가 자연스럽다.
        order_field = definition.get("order_field")
        if order_field and all(field != order_field for field, _ in entries):
            cursor.execute(f"SELECT COALESCE(MAX(`{order_field}`), -1) + 1 AS next_order FROM `{table_name}`")
            entries.append((order_field, cursor.fetchone()["next_order"]))
        columns = ", ".join(f"`{field}`" for field, _ in entries)
        cursor.execute(
            f"INSERT INTO `{table_name}` ({columns}) VALUES ({', '.join(['%s'] * len(entries))})",
            [value for _, value in entries],
        )
        return f"{definition['title']} 항목을 추가했습니다.", "success"

    return apply_write(
        table_name,
        "관리자 데이터 추가 실패",
        "저장하지 못했습니다. 필수 항목과 데이터 형식을 확인하세요.",
        write,
    )


@admin_bp.route("/data/<table_name>/update", methods=["POST"])
@login_required
def update_row(table_name):
    """표에서 고른 행을 같은 양식으로 수정한다.

    대상 행은 서명된 `row_token`으로만 지정할 수 있어 임의의 행을 건드릴 수 없다.
    """
    require_csrf()
    definition = content_table(table_name)
    conditions = target_conditions(definition, request.form.get("row_token", ""))
    if not conditions:
        abort(400, "수정할 행을 특정할 수 없습니다.")

    def write(cursor):
        nullable = nullable_columns(cursor, table_name)
        # 빈 칸은 값을 지우겠다는 뜻이지만, NOT NULL 열은 지울 수 없어 기존 값을 유지한다.
        assignments = []
        for field in definition["fields"]:
            value = request.form.get(field, "").strip()
            if value:
                assignments.append((field, value))
            elif field in nullable:
                assignments.append((field, None))
        if not assignments:
            return "수정할 내용을 입력하세요.", "error"

        where, condition_values = where_clause(conditions)
        # 값이 그대로면 UPDATE의 반영 행 수가 0이므로, 대상 존재 여부는 따로 확인한다.
        cursor.execute(f"SELECT COUNT(*) AS matched FROM `{table_name}` WHERE {where}", condition_values)
        if not cursor.fetchone()["matched"]:
            return "수정할 항목을 찾지 못했습니다. 목록을 새로고침한 뒤 다시 시도하세요.", "error"

        setters = ", ".join(f"`{field}` = %s" for field, _ in assignments)
        cursor.execute(
            f"UPDATE `{table_name}` SET {setters} WHERE {where}",
            [value for _, value in assignments] + condition_values,
        )
        return f"{definition['title']} 항목을 수정했습니다.", "success"

    return apply_write(
        table_name,
        "관리자 데이터 수정 실패",
        "수정하지 못했습니다. 값의 형식과 중복 여부를 확인하세요.",
        write,
    )


@admin_bp.route("/data/<table_name>/delete", methods=["POST"])
@login_required
def delete_row(table_name):
    require_csrf()
    definition = content_table(table_name)
    conditions = target_conditions(definition, request.form.get("row_token", ""))
    if not conditions:
        abort(400)

    def write(cursor):
        where, condition_values = where_clause(conditions)
        cursor.execute(f"DELETE FROM `{table_name}` WHERE {where}", condition_values)
        return "항목을 삭제했습니다.", "success"

    return apply_write(table_name, "관리자 데이터 삭제 실패", "삭제하지 못했습니다.", write)


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
