"""사용자 제보(제안/제보) 제출을 처리하는 공용 핸들러."""

import logging

from flask import jsonify, request

from stelline.apis.turnstile import verify_turnstile
from stelline.database.connection import database_cursor

MAX_REPORT_LENGTH = 2000


def handle_report_submission(table, log_label):
    """캡차 검증 후 제보 내용을 지정한 테이블에 저장한다.

    `table`은 내부에서 지정하는 신뢰된 상수여야 한다(사용자 입력 금지).
    """
    payload = request.get_json(silent=True) or {}
    raw_content = payload.get("content", "")
    content = raw_content.strip() if isinstance(raw_content, str) else ""
    logging.info("%s 제출 요청: content_length=%s", log_label, len(content))

    if not verify_turnstile(payload.get("captcha_token")):
        logging.warning("%s 캡차 인증 실패", log_label)
        return jsonify({"error": "캡차 인증에 실패했습니다. 다시 시도하세요."}), 400

    if not content:
        logging.warning("%s 내용이 비어 있음", log_label)
        return jsonify({"error": "제보 내용을 입력하세요."}), 400

    if len(content) > MAX_REPORT_LENGTH:
        logging.warning("%s 길이 초과: length=%s", log_label, len(content))
        return jsonify({"error": f"제보 내용은 {MAX_REPORT_LENGTH}자 이내로 입력하세요."}), 400

    try:
        with database_cursor() as cursor:
            cursor.execute(f"INSERT INTO {table} (content) VALUES (%s)", (content,))
    except Exception:
        logging.exception("%s 저장 실패", log_label)
        return jsonify({"error": "제보를 저장하지 못했습니다."}), 500

    logging.info("%s 저장 완료: length=%s", log_label, len(content))
    return jsonify({"message": "제보가 접수되었습니다."}), 201
