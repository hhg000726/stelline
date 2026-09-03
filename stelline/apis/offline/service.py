import logging

import requests
from flask import jsonify

from stelline.config import NCP_CLIENT_ID, NCP_CLIENT_SECRET
from stelline.database.connection import database_cursor


def geocode_location(address, client_id, client_secret):
    try:
        headers = {
            "x-ncp-apigw-api-key-id": client_id,
            "x-ncp-apigw-api-key": client_secret
        }
        params = {"query": address.strip()}
        logging.info("Geocode 요청 시작: address=%s", address)
        res = requests.get(
            "https://maps.apigw.ntruss.com/map-geocode/v2/geocode",
            headers=headers,
            params=params,
            timeout=5,
        )
        res.raise_for_status()

        data = res.json()
        addresses = data.get("addresses", [])
        if addresses:
            lat = float(addresses[0]["y"])
            lng = float(addresses[0]["x"])
            logging.info("Geocode 변환 성공: address=%s, lat=%s, lng=%s", address, lat, lng)
            return lat, lng
        logging.warning("[Geocode] 주소 결과 없음: %s", address)
        return None, None

    except requests.exceptions.RequestException as error:
        logging.error("[Geocode] 요청 실패: %s - %s", address, error)
    except (ValueError, KeyError, TypeError) as error:
        logging.error("[Geocode] 응답 파싱 실패: %s - %s", address, error)
    except Exception as error:
        logging.error("[Geocode] 알 수 없는 에러: %s - %s", address, error)

    return None, None


def _needs_geocoding(event):
    lat = event.get("latitude")
    lng = event.get("longitude")
    return (lat is None or lat < 1 or lng is None or lng < 1) and bool(event.get("address"))


def fetch_offline_events():
    """행사 목록을 내려주고, 좌표가 비어 있는 행사는 주소로 좌표를 채워 둔다.

    지오코딩은 한 건에 최대 5초가 걸리는 외부 호출이라 DB 트랜잭션 밖에서 한다.
    (예전에는 커서를 연 채 호출해, 주소가 여러 개면 그동안 커넥션을 붙들고 있었다.)
    채워진 좌표는 마지막에 한 번에 저장한다.
    """
    logging.info("오프라인 행사 데이터 조회 및 좌표 보완 요청")
    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT * FROM offline")
            data = cursor.fetchall()

        updates = []
        for event in data:
            if not _needs_geocoding(event):
                continue
            new_lat, new_lng = geocode_location(event.get("address"), NCP_CLIENT_ID, NCP_CLIENT_SECRET)
            if new_lat and new_lng:
                event["latitude"] = new_lat
                event["longitude"] = new_lng
                updates.append((new_lat, new_lng, event.get("name")))

        if updates:
            with database_cursor() as cursor:
                cursor.executemany(
                    "UPDATE offline SET latitude = %s, longitude = %s WHERE name = %s",
                    updates,
                )

        logging.info("오프라인 행사 데이터 조회 및 좌표 보완 완료: count=%s", len(data))
        return jsonify(data), 200
    except Exception as exc:
        logging.exception("오프라인 행사 데이터 처리 실패")
        return jsonify({"error": str(exc)}), 500
