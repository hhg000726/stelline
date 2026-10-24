import logging
import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from stelline.config import ADMIN_PASSWORD, ADMIN_USERNAME
from stelline.logging_config import events

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _matches(given, expected):
    """비교 시간이 맞은 글자 수에 따라 달라지지 않게 한다. 설정이 비어 있으면 아무도 통과하지 못한다."""
    if not expected:
        return False
    return secrets.compare_digest(given.encode('utf-8'), expected.encode('utf-8'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if _matches(username, ADMIN_USERNAME) & _matches(password, ADMIN_PASSWORD):
            # 로그인 전에 쓰던 세션 값을 이어 쓰지 않는다(세션 고정 방지).
            session.clear()
            session['logged_in'] = True
            # 누가 언제 관리자에 들어왔는지는 운영 기록에 남긴다. 실패는 경고라 오류·경고 목록에도 뜬다.
            events.info('관리자 로그인 성공: username=%s', username)
            return redirect(url_for('admin.admin_index'))
        events.warning('관리자 로그인 실패: username=%s', username)
        flash('로그인 실패!')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    logging.info('관리자 로그아웃 처리 완료')
    return redirect(url_for('auth.login'))