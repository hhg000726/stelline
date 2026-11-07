import logging
import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from stelline.config import ADMIN_PASSWORD, ADMIN_USERNAME
from stelline.logging_config import events

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# 운영 기록에 옮겨 적는 아이디의 최대 길이. 실제 아이디는 이보다 훨씬 짧다.
LOGGED_USERNAME_MAX = 40


def _loggable_username(username):
    """누구나 보낼 수 있는 값이라, 로그에 옮겨 적기 전에 한 줄로 줄이고 길이를 자른다.

    줄바꿈을 그대로 두면 `시각 [수준] {스레드} 내용` 모양의 가짜 줄을 끼워 넣을 수 있다. 관리자 화면의
    '운영 로그'는 그 모양으로 줄을 읽으므로, 가짜 '검색 점검 완료' 같은 줄이 진짜처럼 보인다.
    길이를 자르지 않으면 요청 한 번(본문 상한 8MB)이 로그 파일 세 개에 그만큼씩 쌓인다.
    """
    flat = ''.join(character if character.isprintable() else ' ' for character in username)
    if len(flat) > LOGGED_USERNAME_MAX:
        return flat[:LOGGED_USERNAME_MAX] + '…'
    return flat


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
            events.info('관리자 로그인 성공: username=%s', _loggable_username(username))
            return redirect(url_for('admin.admin_index'))
        events.warning('관리자 로그인 실패: username=%s', _loggable_username(username))
        flash('로그인 실패!')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    logging.info('관리자 로그아웃 처리 완료')
    return redirect(url_for('auth.login'))