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
    cred = credentials.Certificate('path/to/your/serviceAccountKey.json') 
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
        # 1. Firebase에서 토큰 삭제 시도 (Admin SDK 사용)
        try:
            # delete_registration_tokens는 토픽 구독 해지용이며, 인스턴스 자체 삭제는 delete_instance_id 또는 send dry run
            # 더 명확한 방법은 send()에 dry_run=True를 사용하여 invalid token 응답을 받고 DB에서 삭제하는 것입니다.
            # 하지만 클라이언트가 deleteToken()을 이미 호출했다면, 서버에서 다시 호출하는 것은 중복일 수 있습니다.
            # 가장 직접적인 방법은 Instance ID API를 사용하는 것이지만, Admin SDK는 메시징을 통해 토큰을 관리합니다.
            # 일반적으로는 클라이언트의 deleteToken()을 신뢰하고, 서버에서는 DB만 업데이트하거나,
            # 메시지 전송 실패 시 Firebase에서 토큰이 유효하지 않다고 알려줄 때 DB에서 삭제하는 방식이 선호됩니다.
            #
            # 만약 정말로 서버에서 Firebase 인스턴스 ID를 삭제하고 싶다면,
            # Admin SDK의 messaging.send()를 통해 토큰이 invalid하다는 응답을 받은 후,
            # 해당 토큰을 Admin SDK의 Instance ID API를 통해 삭제할 수 있습니다.
            # 하지만 현재 `firebase-admin` 라이브러리의 `messaging` 모듈에 특정 토큰을
            # 직접 삭제하는 Public API는 명시적으로 제공되지 않습니다.
            # (주로 `send` 시점에 무효 토큰 감지 후 삭제 권고)
            #
            # 대안 1: 토픽 구독 해지 (아니라면 관련 없음)
            # if 'your_topic_name' in firebase_admin.messaging.get_subscribed_topics(token):
            #     response = messaging.unsubscribe_from_topic(token, 'your_topic_name')
            #     logging.info(f"Unsubscribed token from topic: {response.success_count} success, {response.failure_count} fail")

            # 대안 2: 유효성 검사 (드라이 런 전송) 후 DB에서만 삭제
            # 이 방법은 토큰이 Firebase에서 더 이상 유효하지 않음을 확인하는 데 사용됩니다.
            # 만약 `deleteToken()`이 클라이언트에서 실패하고, 서버에서만 삭제를 시도한다면 유용합니다.
            
            # dry_run으로 토큰의 유효성 검사
            message = messaging.Message(token=token, data={'_': '_'}, dry_run=True)
            response = messaging.send(message)
            logging.info(f"Firebase dry_run send response for token '{token}': {response}")
            # 이 응답을 기반으로 토큰이 유효하지 않으면 DB에서도 삭제합니다.
            # 예: "messaging/registration-token-not-registered" 에러 코드 등
            
            # 이 시점에서 클라이언트가 이미 deleteToken()을 성공적으로 호출했다면,
            # 서버에서 추가적으로 Firebase에 삭제 요청을 보낼 필요는 없습니다.
            # Firebase 토큰 삭제는 클라이언트 측 `messaging.deleteToken()`이 권장됩니다.
            # 서버는 클라이언트가 보낸 토큰이 더 이상 유효하지 않을 때 DB에서 삭제하는 역할을 하는 것이 일반적입니다.

            # 만약 클라이언트에서 `deleteToken()` 호출을 생략하고 오직 서버에서만 삭제를 원한다면,
            # Instance ID API를 직접 호출해야 합니다.
            # 이는 `firebase-admin` SDK의 messaging 모듈 내에는 없으며,
            # 구글 클라우드 IAM 인증을 거쳐 직접 `https://iid.googleapis.com/v1/web/iid/{token}` 에 DELETE 요청을 보내야 합니다.
            # 이 방식은 더 복잡하며, 일반적으로 클라이언트 측 `deleteToken()`이 더 적절합니다.

        except Exception as firebase_err:
            logging.warning(f"Firebase에서 토큰 삭제 시도 중 경고 또는 오류 발생: {firebase_err}")
            # 이 에러는 클라이언트가 이미 Firebase에서 토큰을 삭제했기 때문에 발생할 수 있습니다.
            # 예를 들어, "Requested entity was not found" 같은 에러는 정상적인 상황일 수 있습니다.
            # 따라서 이 에러가 치명적이지 않다면 다음 단계로 넘어갑니다.
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