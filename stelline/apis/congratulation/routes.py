from flask import request
from stelline.database.db_connection import get_rds_connection
from . import congratulation_bp
from .congratulation import *
import firebase_admin
from firebase_admin import credentials, messaging # Firebase Admin SDK 

# Firebase Admin SDK 초기화 (앱 시작 시 한 번만 수행)
# 이 부분은 실제 앱에서는 Flask 앱 컨텍스트나 별도의 초기화 모듈에 있어야 합니다.
try:
    # 이미 초기화되었는지 확인 (다중 초기화 방지)
    firebase_admin.get_app()
except ValueError:
    # 서비스 계정 키 파일 경로를 정확히 지정해주세요.
    # 예: cred = credentials.Certificate('/path/to/your/serviceAccountKey.json')
    # 개발 환경에서는 환경 변수 등으로 경로를 관리하는 것이 좋습니다.
    # 또는 GAE, Cloud Run 등 Google Cloud 환경에서는 서비스 계정 키 없이도 자동 인증됩니다.
    cred = credentials.Certificate(SERVICE_ACCOUNT_FILE) 
    firebase_admin.initialize_app(cred)
    
@congratulation_bp.route("/congratulations", methods=["GET"])
def congratulation_api():
    return congratulations()

@congratulation_bp.route("/register", methods=["POST"])
def register_token():
    data = request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"error": "Token is missing"}), 400

    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            # 이미 있는지 확인
            check_sql = "SELECT id FROM fcm_tokens WHERE token = %s"
            cursor.execute(check_sql, (token,))
            existing = cursor.fetchone()

            if not existing:
                insert_sql = "INSERT INTO fcm_tokens (token) VALUES (%s)"
                cursor.execute(insert_sql, (token,))
                conn.commit()
                logging.info("New token registered.")
            else:
                logging.info("Token already exists.")

        return jsonify({"message": "Token registered"}), 200

    except Exception as e:
        logging.error(f"FCM 토큰 등록 실패: {e}")
        return jsonify({"error": "DB insert failed"}), 500

    finally:
        conn.close()

@congratulation_bp.route("/unregister", methods=["POST"])
def unregister_token():
    """
    클라이언트로부터 받은 FCM 토큰을 데이터베이스에서 삭제합니다.
    Firebase에서 토큰 삭제는 클라이언트 측에서 이루어지며,
    서버는 자체 DB에서 해당 토큰을 제거합니다.
    """
    data = request.get_json()
    token = data.get("token")
    # 'platform' 필드는 클라이언트에서 전송하지만, 현재 DB 스키마에 없으므로 사용하지 않습니다.
    # platform = data.get("platform")

    if not token:
        # 토큰이 누락된 경우 400 Bad Request 응답
        logging.warning("Unregister request received without token.")
        return jsonify({"error": "Token is missing"}), 400

    conn = None # 연결 초기화
    try:
        conn = get_rds_connection()
        with conn.cursor() as cursor:
            # 1. DB에서 토큰 삭제
            delete_sql = "DELETE FROM fcm_tokens WHERE token = %s"
            cursor.execute(delete_sql, (token,))
            
            rows_affected = cursor.rowcount
            conn.commit() # 변경사항 커밋

            if rows_affected > 0:
                logging.info(f"Token '{token}' successfully removed from DB.")
                # 클라이언트가 이미 Firebase에서 토큰을 삭제했을 가능성이 높으므로
                # 서버는 DB에서 성공적으로 제거되었음을 알립니다.
                return jsonify({"message": "Token unregistered successfully"}), 200
            else:
                # 삭제할 토큰이 DB에 없는 경우
                logging.warning(f"Attempted to unregister non-existent token in DB: '{token}'.")
                # 토큰이 이미 없으므로 성공으로 간주하거나, 상태코드 200을 반환합니다.
                # 이는 프론트엔드에서 토큰 삭제 요청이 성공적으로 처리되었음을 의미합니다.
                return jsonify({"message": "Token not found in DB or already unregistered"}), 200

    except Exception as e:
        # 데이터베이스 작업 중 오류 발생 시 500 Internal Server Error 응답
        logging.error(f"FCM 토큰 DB 삭제 실패: {e}", exc_info=True)
        if conn:
            conn.rollback() # 오류 발생 시 롤백
        return jsonify({"error": "Failed to unregister token in DB"}), 500

    finally:
        if conn:
            conn.close()

@congratulation_bp.route("/check-token", methods=["POST"])
def check_token():
    data = request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"error": "Token is missing"}), 400

    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            check_sql = "SELECT token FROM fcm_tokens WHERE token = %s"
            cursor.execute(check_sql, (token,))
            result = cursor.fetchone()

            if result:
                return jsonify({"valid": True}), 200
            else:
                return jsonify({"valid": False}), 200

    except Exception as e:
        logging.error(f"FCM 토큰 확인 실패: {e}")
        return jsonify({"error": "DB check failed"}), 500

    finally:
        conn.close()
