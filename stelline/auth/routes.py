import logging

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from stelline.config import ADMIN_PASSWORD, ADMIN_USERNAME

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            logging.info('관리자 로그인 성공: username=%s', username)
            return redirect(url_for('admin.admin_index'))
        logging.warning('관리자 로그인 실패: username=%s', username)
        flash('로그인 실패!')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    logging.info('관리자 로그아웃 처리 완료')
    return redirect(url_for('auth.login'))