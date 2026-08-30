import logging
import threading
import time

import requests
from bs4 import BeautifulSoup

from stelline.config import API_CHECK_INTERVAL
from stelline.database.connection import database_cursor

# 백그라운드 작업이 채우고 rank 엔드포인트가 읽는 최신 순위 데이터.
recent_rank_data = {}


def scrape_bugs_favorite(name, url_number):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    page_url = "https://favorite.bugs.co.kr/" + str(url_number)
    response = requests.get(page_url, headers=headers)

    if response.status_code != 200:
        logging.error("Bugs 요청 실패: status=%s", response.status_code)
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    names = [n.get_text(strip=True) for n in soup.select("p.title")]
    counts = [int(c.get_text(strip=True).replace(",", "")) for c in soup.select("span.count")]
    streamings = [
        float(s.get_text(strip=True).replace(",", "").replace("%", ""))
        for s in soup.select("span.streaming")
    ]

    rank = next((i + 1 for i, entry in enumerate(names) if name in entry), None)
    if rank is None:
        logging.warning("Bugs 순위에서 대상을 찾지 못함: %s", name)
        return None

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


def load_targets():
    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT * FROM targets")
            return cursor.fetchall()
    except Exception:
        logging.exception("Bugs 대상 불러오기 오류 발생.")
        return []


def run_bugs_rank_cycle(recent_data):
    """주기적으로 Bugs 응원 순위를 가져와 `recent_data`에 채운다."""
    while True:
        targets = load_targets()
        if targets:
            for target in targets:
                name = target["name"]
                try:
                    new_data = scrape_bugs_favorite(name, target["url_number"])
                    if new_data is None:
                        continue
                    new_data["title"] = target["title"]
                    new_data["url_number"] = target["url_number"]
                    recent_data[name] = new_data
                except Exception as exc:
                    logging.error("bugs 데이터 업데이트 오류: %s", exc)
        else:
            recent_data.clear()

        time.sleep(API_CHECK_INTERVAL)


def start_rank_refresh():
    threading.Thread(
        target=run_bugs_rank_cycle, daemon=True, args=(recent_rank_data,), name="bugs-rank"
    ).start()
