import logging

from flask import jsonify, request
import firebase_admin
from firebase_admin import credentials

from stelline.config import SERVICE_ACCOUNT_FILE
from stelline.database.connection import database_cursor
from . import congratulation_bp
from .service import fetch_recent_congratulations, submit_view_report

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
def register_token():
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    logging.info("FCM 토큰 등록 요청 수신: token_present=%s", bool(token))

    if not token:
        logging.warning("FCM 토큰 등록 요청이 토큰 없이 도착했습니다.")
        return jsonify({"error": "Token is missing"}), 400

    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT token FROM fcm_tokens WHERE token = %s", (token,))
            if cursor.fetchone():
                logging.info("Token already exists: token_length=%s", len(token))
            else:
                cursor.execute("INSERT INTO fcm_tokens (token) VALUES (%s)", (token,))
                logging.info("New token registered: token_length=%s", len(token))
        return jsonify({"message": "Token registered"}), 200
    except Exception:
        logging.exception("FCM 토큰 등록 실패")
        return jsonify({"error": "DB insert failed"}), 500

@congratulation_bp.route("/unregister", methods=["POST"])
def unregister_token():
    """
    클라이언트로부터 받은 FCM 토큰을 데이터베이스에서 삭제합니다.
    Firebase에서 토큰 삭제는 클라이언트 측에서 이루어지며,
    서버는 자체 DB에서 해당 토큰을 제거합니다.
    """
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    logging.info("FCM 토큰 삭제 요청 수신: token_present=%s", bool(token))
    # 'platform' 필드는 클라이언트에서 전송하지만, 현재 DB 스키마에 없으므로 사용하지 않습니다.
    # platform = data.get("platform")

    if not token:
        # 토큰이 누락된 경우 400 Bad Request 응답
        logging.warning("Unregister request received without token.")
        return jsonify({"error": "Token is missing"}), 400

    try:
        with database_cursor() as cursor:
            cursor.execute("DELETE FROM fcm_tokens WHERE token = %s", (token,))
            rows_affected = cursor.rowcount

        if rows_affected > 0:
            logging.info("Token successfully removed from DB.")
            return jsonify({"message": "Token unregistered successfully"}), 200
        logging.warning("Attempted to unregister non-existent token in DB.")
        return jsonify({"message": "Token not found in DB or already unregistered"}), 200
    except Exception:
        logging.exception("FCM 토큰 DB 삭제 실패")
        return jsonify({"error": "Failed to unregister token in DB"}), 500

@congratulation_bp.route("/check-token", methods=["POST"])
def check_token():
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    logging.info("FCM 토큰 확인 요청 수신: token_present=%s", bool(token))

    if not token:
        logging.warning("FCM 토큰 확인 요청이 토큰 없이 도착했습니다.")
        return jsonify({"error": "Token is missing"}), 400

    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT token FROM fcm_tokens WHERE token = %s", (token,))
            is_valid = cursor.fetchone() is not None
        logging.info("FCM 토큰 확인 성공: token_present=%s", is_valid)
        return jsonify({"valid": is_valid}), 200
    except Exception:
        logging.exception("FCM 토큰 확인 실패")
        return jsonify({"error": "DB check failed"}), 500
