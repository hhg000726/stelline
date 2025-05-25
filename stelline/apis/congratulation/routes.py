from flask import request

from stelline.database import db_connection
from . import congratulation_bp
from .congratulation import *

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
    """
    data = request.get_json()
    token = data.get("token")
    # 'platform' 필드는 클라이언트에서 전송하지만, 현재 DB 스키마에 없으므로 사용하지 않습니다.
    # platform = data.get("platform") 

    if not token:
        # 토큰이 누락된 경우 400 Bad Request 응답
        logging.warning("Unregister request received without token.")
        return jsonify({"error": "Token is missing"}), 400

    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            # 토큰을 삭제하는 SQL 쿼리
            delete_sql = "DELETE FROM fcm_tokens WHERE token = %s"
            cursor.execute(delete_sql, (token,))
            
            # 삭제된 행의 개수 확인
            rows_affected = cursor.rowcount 
            conn.commit()

            if rows_affected > 0:
                logging.info(f"Token '{token}' unregistered successfully.")
                return jsonify({"message": "Token unregistered"}), 200
            else:
                # 삭제할 토큰이 DB에 없는 경우
                logging.warning(f"Attempted to unregister non-existent token: '{token}'.")
                return jsonify({"message": "Token not found or already unregistered"}), 200 # 또는 404 Not Found

    except Exception as e:
        # 데이터베이스 작업 중 오류 발생 시 500 Internal Server Error 응답
        logging.error(f"FCM 토큰 삭제 실패: {e}", exc_info=True) # exc_info=True로 스택 트레이스 기록
        return jsonify({"error": "DB deletion failed"}), 500

    finally:
        # 연결이 성공적으로 이루어졌다면 반드시 닫아줍니다.
        if conn:
            conn.close()