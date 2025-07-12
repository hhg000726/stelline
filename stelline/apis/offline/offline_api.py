import logging
import requests
from flask import jsonify

from stelline.config import NCP_CLIENT_ID, NCP_CLIENT_SECRET
from stelline.database.db_connection import get_rds_connection

# 주소 → 위경도 변환
def geocode_location(address, client_id, client_secret):
    try:
        headers = {
            "x-ncp-apigw-api-key-id": client_id,
            "x-ncp-apigw-api-key": client_secret
        }
        params = {"query": address.strip()}
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
            return lat, lng
        else:
            logging.warning(f"[Geocode] 주소 결과 없음: {address}")
            return None, None

    except requests.exceptions.RequestException as e:
        logging.error(f"[Geocode] 요청 실패: {address} - {str(e)}")
    except (ValueError, KeyError, TypeError) as e:
        logging.error(f"[Geocode] 응답 파싱 실패: {address} - {str(e)}")
    except Exception as e:
        logging.error(f"[Geocode] 알 수 없는 에러: {address} - {str(e)}")
    
    return None, None

def offline_api():

    conn = get_rds_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 모든 이벤트 조회
            cursor.execute("SELECT * FROM offline")
            data = cursor.fetchall()

            for event in data:
                lat = event.get("latitude")
                lng = event.get("longitude")
                location_name = event.get("location_name")
                name = event.get("name")

                # 2. 위경도가 비어있다면 → Geocode 호출
                if (lat < 1 or lng < 1) and location_name:
                    new_lat, new_lng = geocode_location(location_name, NCP_CLIENT_ID, NCP_CLIENT_SECRET)
                    if new_lat and new_lng:
                        update_sql = """
                            UPDATE offline
                            SET latitude = %s, longitude = %s
                            WHERE name = %s
                        """
                        cursor.execute(update_sql, (new_lat, new_lng, name))
                        event["latitude"] = new_lat
                        event["longitude"] = new_lng

            conn.commit()  # ✅ UPDATE 반영

            return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()