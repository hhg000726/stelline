import logging

import requests
from flask import jsonify

from stelline.config import NCP_CLIENT_ID, NCP_CLIENT_SECRET
from stelline.database.connection import database_cursor

# 주소 → 위경도 변환
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
            timeout=5  # ⏱️ 요청 제한 시간 설정 (옵션)
        )

        res.raise_for_status()  # HTTP 에러 발생 시 예외 던짐

        data = res.json()
        addresses = data.get("addresses", [])
        if addresses:
            lat = float(addresses[0]["y"])
            lng = float(addresses[0]["x"])
            logging.info("Geocode 변환 성공: address=%s, lat=%s, lng=%s", address, lat, lng)
            return lat, lng
        logging.warning("[Geocode] 주소 결과 없음: %s", address)
        return None, None

    except requests.exceptions.RequestException as e:
        logging.error("[Geocode] 요청 실패: %s - %s", address, str(e))
    except (ValueError, KeyError, TypeError) as e:
        logging.error("[Geocode] 응답 파싱 실패: %s - %s", address, str(e))
    except Exception as e:
        logging.error("[Geocode] 알 수 없는 에러: %s - %s", address, str(e))

    return None, None


def fetch_offline_events():
    logging.info("오프라인 행사 데이터 조회 및 좌표 보완 요청")
    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT * FROM offline")
            data = cursor.fetchall()

            for event in data:
                lat = event.get("latitude")
                lng = event.get("longitude")
                address = event.get("address")
                name = event.get("name")

                if (lat is None or lat < 1 or lng is None or lng < 1) and address:
                    new_lat, new_lng = geocode_location(address, NCP_CLIENT_ID, NCP_CLIENT_SECRET)
                    if new_lat and new_lng:
                        cursor.execute(
                            "UPDATE offline SET latitude = %s, longitude = %s WHERE name = %s",
                            (new_lat, new_lng, name),
                        )
                        event["latitude"] = new_lat
                        event["longitude"] = new_lng

        logging.info("오프라인 행사 데이터 조회 및 좌표 보완 완료: count=%s", len(data))
        return jsonify(data), 200
    except Exception as exc:
        logging.exception("오프라인 행사 데이터 처리 실패")
        return jsonify({"error": str(exc)}), 500
