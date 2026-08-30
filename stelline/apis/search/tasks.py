import json
import logging
import os
import random
import re
import threading
import time

import requests

from stelline.config import SEARCH_API_INTERVAL, SEARCH_API_KEY, TEMP_API_KEY
from stelline.database.connection import database_cursor

LAST_SEARCH_FILE = "last_search_time.txt"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def read_last_search_timestamp():
    try:
        if not os.path.exists(LAST_SEARCH_FILE):
            with open(LAST_SEARCH_FILE, "w", encoding="utf-8") as file:
                file.write("0")
            return 0

        with open(LAST_SEARCH_FILE, "r", encoding="utf-8") as file:
            return float(file.read().strip())
    except OSError:
        logging.error("마지막 검색 시간 불러오기 실패")
        return 0


def write_last_search_timestamp(timestamp):
    with open(LAST_SEARCH_FILE, "w", encoding="utf-8") as file:
        file.write(str(timestamp))


last_search_timestamp = read_last_search_timestamp()


def fetch_song_infos_from_db():
    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT * FROM song_infos")
            return cursor.fetchall()
    except Exception:
        logging.exception("RDS 곡 정보 불러오기 실패")
        return []


def fetch_songs_data_from_db():
    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT * FROM songs_data")
            rows = cursor.fetchall()
        all_songs = [{"query": row.get("query"), "video_id": row.get("video_id")} for row in rows]
        return all_songs, last_search_timestamp
    except Exception:
        logging.exception("RDS songs 정보 불러오기 실패")
        return [], 0


def fetch_recent_data_from_db():
    try:
        with database_cursor() as cursor:
            cursor.execute("SELECT * FROM recent_data")
            return cursor.fetchall()
    except Exception:
        logging.exception("RDS recent 정보 불러오기 실패")
        return []


def update_song_risk(query, risk):
    try:
        with database_cursor() as cursor:
            cursor.execute("UPDATE song_infos SET risk = %s WHERE query = %s", (risk, query))
    except Exception:
        logging.exception("RDS risk 업데이트 실패")


def _youtube_video_ids_for_query(query, api_key):
    """YouTube Data API 검색 결과에서 상위 영상 ID 목록을 반환한다."""
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 3,
        "key": api_key,
    }
    response = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=10)
    response.raise_for_status()
    items = response.json().get("items", [])
    return [item["id"]["videoId"] for item in items if "id" in item]


def _resolve_match(query, video_id, video_ids, song_risk):
    """영상이 검색 결과에 있으면 risk를 낮추고 True, 없으면 28로 올리고 False를 반환한다."""
    if video_id in video_ids:
        update_song_risk(query, max(song_risk - 1, 0))
        return True
    update_song_risk(query, 28)
    return False


def crawl_search_results_for_missing_videos(songs):
    not_searched = []
    base_url = "https://www.youtube.com/results"
    headers = {"User-Agent": "Mozilla/5.0"}

    for case in songs:
        time.sleep(random.uniform(3, 8))
        query = case["query"]
        params = {"search_query": query}
        video_id = case["video_id"]
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            html = response.text
            match = re.search(r"ytInitialData\s*=\s*({.*?});", html, re.DOTALL)
            if not match:
                logging.error("크롤링 데이터 파싱 실패: %s", query)
                continue
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                logging.error("JSON 파싱 실패: %s", query)
                continue

            video_ids = []
            contents = (
                data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )
            for section in contents:
                if len(video_ids) >= 3:
                    break
                items = section.get("itemSectionRenderer", {}).get("contents", [])
                for item in items:
                    if len(video_ids) >= 3:
                        break
                    video = item.get("videoRenderer")
                    if video:
                        video_ids.append(video["videoId"])

            if not _resolve_match(query, video_id, video_ids, case.get("risk", 0)):
                not_searched.append({"query": query, "video_id": video_id})

        except requests.RequestException as exc:
            logging.error("크롤링 실패: %s", exc)
            return {"all_songs": songs, "searched_time": time.time()}

    return {"all_songs": not_searched, "searched_time": time.time()}


def search_unverified_songs(by_admin=False):
    is_quota_exceeded = False

    song_infos = fetch_song_infos_from_db()
    logging.info("검색 시작")
    not_searched = []
    search_targets = []
    risk_zero_songs = [info for info in song_infos if info.get("risk") == 0]

    for risk_level in reversed(range(1, 29)):
        search_targets.extend([info for info in song_infos if info.get("risk") == risk_level])
        if len(search_targets) >= 12:
            search_targets = search_targets[:12]
            break

    remaining_quotes = 25

    if by_admin:
        logging.info("관리자 즉시 검색 실행")
        selected_api_key = TEMP_API_KEY
    else:
        logging.info("자동 즉시 검색 실행")
        if not SEARCH_API_KEY:
            logging.error("자동 검색용 YouTube API 키가 설정되지 않았습니다.")
            return {"all_songs": [], "searched_time": time.time(), "isQuotaExceeded": True}
        selected_api_key = random.choice(SEARCH_API_KEY)

    logging.info("[1차 검사 시작] risk_zero_songs=%s, search_targets=%s", len(risk_zero_songs), len(search_targets))

    while remaining_quotes > len(not_searched) + 1:
        song = None

        if search_targets:
            song = search_targets.pop(0)
        else:
            if not risk_zero_songs:
                break
            song = risk_zero_songs.pop(random.randrange(len(risk_zero_songs)))

        if not song:
            break

        time.sleep(20)

        query = song["query"]
        video_id = song["video_id"]

        try:
            logging.info(
                "API 요청 시도 query=%s, video_id=%s, remainingQuotes=%s, not_searched=%s",
                query,
                video_id,
                remaining_quotes,
                len(not_searched),
            )
            video_ids = _youtube_video_ids_for_query(query, selected_api_key)
            if not _resolve_match(query, video_id, video_ids, song["risk"]):
                not_searched.append({"query": query, "video_id": video_id, "risk": song["risk"]})
            remaining_quotes -= 1
        except requests.RequestException as exc:
            is_quota_exceeded = True
            logging.error("API 요청 실패: %s", exc)
            break

    logging.info("[1차 검사 종료] remainingQuotes=%s, not_searched=%s", remaining_quotes, len(not_searched))

    idx = 0
    while idx < len(not_searched) and remaining_quotes > 0:
        time.sleep(20)
        song = not_searched[idx]
        query = song["query"]
        video_id = song["video_id"]

        try:
            logging.info(
                "API 재시도 query=%s, video_id=%s, remainingQuotes=%s, not_searched=%s",
                query,
                video_id,
                remaining_quotes,
                len(not_searched),
            )
            video_ids = _youtube_video_ids_for_query(query, selected_api_key)
            if _resolve_match(query, video_id, video_ids, song["risk"]):
                not_searched.pop(idx)
            else:
                idx += 1
            remaining_quotes -= 1
        except requests.RequestException as exc:
            idx += 1
            is_quota_exceeded = True
            logging.error("API 요청 실패: %s", exc)
            break

    logging.info("[2차 검사 종료] remainingQuotes=%s, not_searched=%s", remaining_quotes, len(not_searched))

    not_searched = crawl_search_results_for_missing_videos(not_searched)["all_songs"]
    logging.info("[최종 결과] 총 실패곡=%s", len(not_searched))

    return {"all_songs": not_searched, "searched_time": time.time(), "isQuotaExceeded": is_quota_exceeded}


# 주기적으로 검색 데이터 가져오기
def run_search_cycle(by_admin=False):
    logging.info("주기적 검색 시작됨")
    global last_search_timestamp

    while True:
        try:
            new_songs = search_unverified_songs(by_admin)

            if new_songs.get("isQuotaExceeded"):
                logging.info("쿼터 초과")
            else:
                last_search_timestamp = new_songs["searched_time"]
                write_last_search_timestamp(last_search_timestamp)
                all_songs = new_songs["all_songs"]
                save_search_results_to_db(all_songs, new_songs["searched_time"])
                logging.info("검색 데이터 업데이트 완료!")
        except Exception as exc:
            logging.error("검색 업데이트 오류: %s", exc)

        if by_admin:
            break

        wait_until_next_search_interval()


def save_search_results_to_db(all_songs, searched_time):
    try:
        with database_cursor() as cursor:
            cursor.execute("TRUNCATE TABLE songs_data")

            cursor.executemany(
                "INSERT INTO songs_data (video_id, query, searched_time) VALUES (%s, %s, %s)",
                [
                    (item.get("video_id", ""), item.get("query", ""), searched_time)
                    for item in all_songs
                ],
            )

            cursor.execute(
                """
                INSERT INTO recent_data (video_id, query, searched_time)
                SELECT video_id, query, searched_time
                FROM songs_data
                ON DUPLICATE KEY UPDATE
                    searched_time = VALUES(searched_time)
                """
            )
    except Exception:
        logging.exception("RDS search 업데이트 실패")


def wait_until_next_search_interval():
    time.sleep(SEARCH_API_INTERVAL - time.time() % SEARCH_API_INTERVAL)


def start_delayed_search(delay):
    time.sleep(delay)
    logging.info("%s초 후 API 검색 시작", delay)
    run_search_cycle()


def schedule_initial_search():
    delay = max(5, SEARCH_API_INTERVAL - time.time() % SEARCH_API_INTERVAL)
    hours, remainder = divmod(int(delay), 3600)
    minutes, seconds = divmod(remainder, 60)
    logging.info("첫 검색을 %d:%02d:%02d 만큼 지연..", hours, minutes, seconds)
    threading.Thread(target=start_delayed_search, daemon=True, args=(delay,)).start()


def start_search_scheduler():
    logging.info("검색 스케줄러 초기화 시작")
    schedule_initial_search()
