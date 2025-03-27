from flask import Blueprint, render_template, session, redirect, url_for
from functools import wraps
from stelline.database.db_connection import get_rds_connection  # 이미 있는 pymysql 연결 함수 사용

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)
    return wrapped

@admin_bp.route('/')
@login_required
def admin_index():
    conn = get_rds_connection()
    table_names = [
        "song_infos", "songs_data", "recent_data", "record_main",
        "record_search", "leaderboard", "targets"
    ]
    data = {}

    with conn.cursor() as cursor:
        for table in table_names:
            cursor.execute(f"SELECT * FROM {table}")
            data[table] = cursor.fetchall()

    conn.close()
    return render_template('admin/index.html', data=data)