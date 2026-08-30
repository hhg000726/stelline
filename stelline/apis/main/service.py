import logging

from flask import jsonify

from stelline.database.connection import database_cursor


def increment_main_page_visits():
    logging.info("메인 페이지 조회수 증가 요청")
    try:
        with database_cursor() as cursor:
            cursor.execute("UPDATE record_main SET copy_count = copy_count + 1")
        logging.info("메인 페이지 조회수 증가 완료")
    except Exception:
        logging.exception("RDS record_main copy_count 업데이트 실패")

    return '', 204


def _fetch_all(table, log_label):
    try:
        with database_cursor() as cursor:
            cursor.execute(f"SELECT * FROM {table}")
            result = cursor.fetchall()
        logging.info("%s 조회 성공: count=%s", log_label, len(result))
        return jsonify(result)
    except Exception:
        logging.exception("%s 불러오기 실패", log_label)
        return jsonify([])


def fetch_events():
    logging.info("이벤트 목록 조회 요청")
    return _fetch_all("events", "이벤트 목록")


def fetch_twits():
    logging.info("트윗 목록 조회 요청")
    return _fetch_all("twits", "트윗 목록")


def fetch_main_buttons():
    """메인 화면 상단 버튼의 표시 여부와 순서를 내려준다.

    조회에 실패하면 빈 목록을 주고, 화면은 HTML에 적힌 기본 상태를 그대로 보여준다.
    """
    logging.info("메인 버튼 설정 조회 요청")
    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT button_key, label, visible, display_order FROM main_buttons ORDER BY display_order, button_key")
            rows = cursor.fetchall()
        logging.info("메인 버튼 설정 조회 성공: count=%s", len(rows))
        return jsonify([
            {"key": row["button_key"], "label": row["label"], "visible": bool(row["visible"]), "order": row["display_order"]}
            for row in rows
        ])
    except Exception:
        logging.exception("메인 버튼 설정 불러오기 실패")
        return jsonify([])
