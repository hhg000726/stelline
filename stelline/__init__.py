from flask import Flask
from flask_cors import CORS
import logging

from stelline.logging_config import setup_logging
from stelline.config import SECRET_KEY
from stelline.database.db_connection import get_rds_connection

# 로깅 설정
setup_logging()

from stelline.apis import api_bp  # 여러 개의 API 블루프린트를 포함하는 Blueprint
from stelline.admin import admin_bp
from stelline.auth import auth_bp

# 기존 핸들러 유지 (Flask가 덮어쓰지 않도록 설정)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.DEBUG)

# Flask 앱 생성
app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

# RDS 연결 설정
from stelline.database.db_connection import get_rds_connection

conn = get_rds_connection()
with conn.cursor() as cursor:
    try:
        cursor.execute("DELETE FROM offline WHERE address IS NULL")
        conn.commit()
        logging.info("오프라인 테이블에 address 컬럼 추가 완료.")
    except Exception as e:
        logging.error(f"오프라인 테이블에 address 컬럼 추가 중 오류 발생: {e}")
    finally:
        conn.close()

# Flask 기본 로거 활성화
app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(logging.StreamHandler())

# API 블루프린트 등록
app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(auth_bp, url_prefix="/auth")

logging.info("Flask 앱 초기화 완료.")