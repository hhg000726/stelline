import requests
from flask import jsonify

from stelline.config import NCP_CLIENT_ID, NCP_CLIENT_SECRET
from stelline.database.db_connection import get_rds_connection

# 주소 → 위경도 변환
def geocode_location(address, client_id, client_secret):
    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret
    }
    params = {"query": address}
    res = requests.get("https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode", headers=headers, params=params)
    data = res.json()
    if data.get("addresses"):
        lat = float(data["addresses"][0]["y"])
        lng = float(data["addresses"][0]["x"])
        return lat, lng
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
                if (lat is None or lng is None) and location_name:
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