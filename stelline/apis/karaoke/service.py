"""노래방 번호 목록 조회와 사용자 제보·복사 기록을 처리한다."""

import hashlib
import json
import logging

from flask import jsonify, make_response, request

from stelline.apis.reports import handle_report_submission
from stelline.database.connection import database_cursor

SONG_QUERY = """
    SELECT id, title, title_alt, artist, members, section, category, tj, ky, note, sort_order, updated_at
      FROM karaoke_songs
     ORDER BY sort_order, id
"""


def _split_members(value):
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _serialize_song(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "titleAlt": row["title_alt"] or "",
        "artist": row["artist"],
        "members": _split_members(row["members"]),
        "section": row["section"],
        "category": row["category"],
        "tj": row["tj"] or "",
        "ky": row["ky"] or "",
        "note": row["note"] or "",
    }


def _member_list(members, songs):
    """멤버 마스터를 쓰되, 비어 있으면 곡에 적힌 멤버 이름으로 대신 채운다."""
    if members:
        return [
            {
                "name": row["name"],
                "unit": row["unit"] or "",
                "formerUnits": [part.strip() for part in (row["former_units"] or "").split(",") if part.strip()],
            }
            for row in members
        ]
    names = []
    for row in songs:
        for name in _split_members(row["members"]):
            if name not in names:
                names.append(name)
    return [{"name": name, "unit": "", "formerUnits": []} for name in sorted(names)]


def fetch_songs():
    """곡 목록과 멤버 마스터를 한 번에 내려준다.

    전체가 수백 곡 규모라 클라이언트가 한 번 받아 두고 검색·필터를 처리한다.
    ETag를 붙여 두 번째 방문부터는 304로 끝난다.
    """
    logging.info("노래방 번호 목록 조회 요청")
    try:
        with database_cursor() as cursor:
            cursor.execute(SONG_QUERY)
            songs = cursor.fetchall()
            # 졸업 여부는 데이터 검증용이라 공개 화면에는 내려보내지 않는다.
            cursor.execute(
                "SELECT name, unit, former_units, display_order"
                " FROM karaoke_members ORDER BY display_order, name"
            )
            members = cursor.fetchall()
    except Exception as exc:
        logging.exception("노래방 번호 목록 조회 실패")
        return jsonify({"error": str(exc)}), 500

    updated_at = max((row["updated_at"] for row in songs if row["updated_at"]), default=None)
    payload = {
        "songs": [_serialize_song(row) for row in songs],
        "members": _member_list(members, songs),
        "updatedAt": updated_at.isoformat(sep=" ", timespec="seconds") if updated_at else "",
    }

    body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    response = make_response(body)
    response.mimetype = "application/json"
    response.set_etag(hashlib.sha256(body.encode("utf-8")).hexdigest())
    response.cache_control.public = True
    response.cache_control.max_age = 60
    logging.info("노래방 번호 목록 조회 완료: songs=%s, members=%s", len(payload["songs"]), len(payload["members"]))
    return response.make_conditional(request)


def submit_karaoke_report():
    return handle_report_submission("karaoke_reports", "노래방 번호 제보")


def record_copy():
    """번호 복사 횟수를 누적한다. 실패해도 화면 동작에는 영향을 주지 않는다."""
    try:
        with database_cursor() as cursor:
            cursor.execute("UPDATE record_karaoke SET copy_count = copy_count + 1")
    except Exception:
        logging.exception("노래방 번호 복사 기록 실패")
        return jsonify({"error": "기록하지 못했습니다."}), 500
    return jsonify({"message": "기록했습니다."}), 200
