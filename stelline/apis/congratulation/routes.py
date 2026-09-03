import logging

import firebase_admin
from firebase_admin import credentials

from stelline.config import SERVICE_ACCOUNT_FILE
from . import congratulation_bp
from .service import (
    check_token,
    fetch_recent_congratulations,
    register_token,
    submit_view_report,
    unregister_token,
)

# Firebase Admin SDK 초기화 (앱 시작 시 한 번만 수행)
# 개발 환경에서는 service-account 파일이 없을 수 있으므로, 그 경우에는
# FCM 기능만 비활성화하고 앱은 계속 시작되도록 처리한다.
if SERVICE_ACCOUNT_FILE:
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(credentials.Certificate(SERVICE_ACCOUNT_FILE))
else:
    logging.warning("Firebase 서비스 계정이 없어 FCM 초기화를 건너뜁니다.")


@congratulation_bp.route("/congratulations", methods=["GET"])
def congratulation_api():
    return fetch_recent_congratulations()


@congratulation_bp.route("/reports", methods=["POST"])
def submit_view_report_api():
    return submit_view_report()


@congratulation_bp.route("/register", methods=["POST"])
def register_token_api():
    return register_token()


@congratulation_bp.route("/unregister", methods=["POST"])
def unregister_token_api():
    return unregister_token()


@congratulation_bp.route("/check-token", methods=["POST"])
def check_token_api():
    return check_token()
