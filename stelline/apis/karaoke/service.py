"""노래방 번호 목록 조회와 사용자 제보·복사 기록을 처리한다."""

import hashlib
import json
import logging
from datetime import timedelta

from flask import jsonify, make_response, request

from stelline.apis.reports import handle_report_submission
from stelline.database.connection import database_cursor

SONG_QUERY = """
    SELECT id, title, title_alt, artist, members, section, category, tj, ky, updated_at
      FROM karaoke_songs
     ORDER BY id
"""

# updated_at 은 DB가 CURRENT_TIMESTAMP 로 적는 값이고, 그 서버는 UTC 로 돈다.
# 그대로 내려보내면 화면의 '마지막 갱신'이 아홉 시간 이르게 적혀, 방금 고친 번호가
# 어제 것처럼 보인다. 읽는 사람이 한국에 있으므로 한국 시간으로 옮겨 내려보낸다.
# (한국은 서머타임이 없어 한 해 내내 +9 로 일정하다. 그래서 tz 이름을 들고 오지 않고
#  더하기 한 번으로 끝낸다.)
KST_OFFSET = timedelta(hours=9)


def _updated_at_text(rows):
    """가장 나중에 고친 시각을 한국 시간 문자열로 만든다. 없으면 빈 문자열이다."""
    latest = max((row["updated_at"] for row in rows if row["updated_at"]), default=None)
    if not latest:
        return ""
    return (latest + KST_OFFSET).isoformat(sep=" ", timespec="seconds")


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
    # 어차피 마지막에 정렬하므로 순서를 지킬 필요가 없다. 리스트 검색(O(n^2)) 대신 집합을 쓴다.
    names = set()
    for row in songs:
        names.update(_split_members(row["members"]))
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

    payload = {
        "songs": [_serialize_song(row) for row in songs],
        "members": _member_list(members, songs),
        "updatedAt": _updated_at_text(songs),
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
