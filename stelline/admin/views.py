from flask import Blueprint, render_template, session, redirect, url_for, request
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
        "record_search", "leaderboard", "targets", "events"
    ]
    data = {}
    columns = {}

    with conn.cursor() as cursor:
        for table in table_names:
            cursor.execute(f"SELECT * FROM {table}")
            data[table] = cursor.fetchall()
            cursor.execute(f"SHOW COLUMNS FROM {table}")
            columns[table] = [row['Field'] for row in cursor.fetchall()]

    conn.close()
    return render_template('admin/index.html', data=data, columns=columns)

@admin_bp.route('/delete/<table_name>', methods=['POST'])
@login_required
def delete_row(table_name):
    conn = get_rds_connection()
    with conn.cursor() as cursor:
        conditions = " AND ".join([f"{key}=%s" for key in request.form.keys()])
        values = list(request.form.values())
        cursor.execute(f"DELETE FROM {table_name} WHERE {conditions}", values)
        conn.commit()
        conn.close()
        return redirect(url_for('admin.admin_index'))

@admin_bp.route('/add/<table_name>', methods=['POST'])
@login_required
def add_row(table_name):
    conn = get_rds_connection()
    cursor = conn.cursor()
    keys = ", ".join(request.form.keys())
    placeholders = ", ".join(["%s"] * len(request.form))
    values = list(request.form.values())
    cursor.execute(f"INSERT INTO {table_name} ({keys}) VALUES ({placeholders})", values)
    conn.commit()
    conn.close()
    return redirect(url_for('admin.admin_index'))