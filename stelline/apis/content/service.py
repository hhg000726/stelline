"""공개 화면이 읽어 가는 사이트 문구·그림."""

import logging

from flask import Response, jsonify, request

from stelline.content import load_image, resolve_items


def fetch_site_contents():
    """모든 항목의 표시값을 한 번에 내려준다.

    실패해도 예외를 내지 않는다(`resolve_items` 가 기본값으로 답한다). 화면은 값을 못 받으면
    HTML에 적힌 기본값을 그대로 쓰므로, 어느 쪽으로 실패해도 빈 화면이 되지 않는다.
    """
    logging.info("사이트 콘텐츠 조회 요청")
    response = jsonify(resolve_items())
    # 관리자가 고치면 곧바로 보여야 한다. 매번 새로 확인하게 둔다.
    response.headers["Cache-Control"] = "no-cache"
    return response


def fetch_site_content_image(key):
    """관리자가 올린 그림 원본. 없으면 404라서 화면은 HTML의 기본 그림을 그대로 쓴다."""
    try:
        row = load_image(key)
    except Exception:
        logging.exception("사이트 콘텐츠 그림 조회 실패: %s", key)
        return "", 404
    if not row:
        return "", 404

    response = Response(row["image_data"], mimetype=row["image_mime"])
    # 주소에 붙은 v= 값이 바뀌면 새 그림을 받는다. 그 사이에는 오래 캐시해도 안전하다.
    response.headers["Cache-Control"] = "public, max-age=86400" if request.args.get("v") else "no-cache"
    # 사용자가 올린 바이트다. 브라우저가 형식을 다시 추측하지 못하게 막는다.
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
