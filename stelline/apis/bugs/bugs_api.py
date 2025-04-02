from bs4 import BeautifulSoup
import requests, logging, time, json

from stelline.config import *
from stelline.database.db_connection import get_rds_connection

def bugs_api(name, url_number):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    page_url = "https://favorite.bugs.co.kr/" + str(url_number)
    response = requests.get(page_url, headers=headers)

    # 응답 확인
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        names = [name.get_text(strip=True) for name in soup.select("p.title")]

        counts = list(map(int, [count.get_text(strip=True).replace(",", "") for count in soup.select("span.count")]))

        streamings = list(map(float, [streaming.get_text(strip=True).replace(",", "").replace("%", "") for streaming in soup.select("span.streaming")]))

        for i in range(len(names)):
            if name in names[i]:
                rank = i + 1
                break
        
        message = soup.select_one(".cheerupMessage span em").get_text(strip=True)

        diffs = {}

        if rank > 1:
            diffs["count_diff"] = round(counts[rank - 2] - counts[rank - 1], 2)
            diffs["count_to_first"] = round(counts[0] - counts[rank - 1], 2)

        if rank > 2:
            diffs["count_to_second"] = round(counts[1] - counts[rank - 1], 2)

        if streamings:            
            if rank > 1:
                diffs["streaming_diff"] = round(streamings[rank - 2] - streamings[rank - 1], 2)
                diffs["streaming_to_first"] = round(streamings[0] - streamings[rank - 1], 2)

            if rank > 2:
                diffs["streaming_to_second"] = round(streamings[1] - streamings[rank - 1], 2)
        
        return {"rank": rank, "message": message, "diffs": diffs}

    else:
        print(f"오류 발생: {response.status_code}")

def load_targets():
    try:
        conn = get_rds_connection()
        with conn.cursor() as cursor:
            sql = "SELECT * FROM targets"
            cursor.execute(sql)
            targets = cursor.fetchall()
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error("벅스 타켓 불러오기 오류 발생.")
        targets = []
    return targets

# 주기적으로 벅스 데이터 가져오기
def bugs_api_process(recent_data):
    while True:
        targets = load_targets()
        for target in targets:
            name = target["name"]
            title = target["title"]
            url_number = target["url_number"]
            try:
                new_data = bugs_api(name, url_number)
                recent_data[name] = new_data
                recent_data[name]["title"] = title
                recent_data[name]["url_number"] = url_number
            except Exception as e:
                logging.error(f"bugs 데이터 업데이트 오류: {e}")
        
        time.sleep(API_CHECK_INTERVAL)