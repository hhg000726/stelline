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