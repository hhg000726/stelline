from bs4 import BeautifulSoup
import requests, logging, time, json

from stelline.config import *

def bugs_api(name, url_number):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    page_url = "https://favorite.bugs.co.kr/" + url_number
    response = requests.get(page_url, headers=headers)

    # 응답 확인
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        names = [name.get_text(strip=True) for name in soup.select("p.title")]

        counts = list(map(int, [count.get_text(strip=True).replace(",", "") for count in soup.select("span.count")]))

        streamings = list(map(float, [streaming.get_text(strip=True).replace(",", "").replace("%", "") for streaming in soup.select("span.streaming")]))

        for i in range(len(names)):
            if names[i] == name:
                rank = i + 1
                break
        
        message = soup.select_one(".cheerupMessage span em").get_text(strip=True)

        diffs = {}

        if rank > 1:
            diffs["count_diff"] = counts[rank - 2] - counts[rank - 1]
            diffs["count_to_first"] = counts[0] - counts[rank - 1]

        if rank > 2:
            diffs["count_to_second"] = counts[1] - counts[rank - 1]

        if streamings:            
            if rank > 1:
                diffs["streaming_diff"] = streamings[rank - 2] - streamings[rank - 1]
                diffs["streaming_to_first"] = streamings[0] - streamings[rank - 1]

            if rank > 2:
                diffs["streaming_to_second"] = streamings[1] - streamings[rank - 1]
        
        return {"rank": rank, "message": message, "diffs": diffs}

    else:
        print(f"오류 발생: {response.status_code}")

# targets 로드
def load_targets():
    if os.path.exists(TARGETS_FILE):
        try:
            with open(TARGETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logging.error("TARGETS_FILE 불러오기 실패")
            return {}

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
                if new_data and new_data != recent_data.get(name):
                    recent_data[name] = new_data
                    recent_data[name]["title"] = title
                    recent_data[name]["url_number"] = url_number
                    logging.info(f"벅스 {name} {title} 데이터 업데이트 완료!")
                else:
                    logging.info(f"벅스 {name} 새로운 데이터 없음, 기존 데이터를 유지")
            except Exception as e:
                logging.error(f"YouTube API 업데이트 오류: {e}")
        
        time.sleep(API_CHECK_INTERVAL)