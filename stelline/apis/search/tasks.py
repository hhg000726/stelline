import json
import logging
import os
import random
import re
import threading
import time
from collections import defaultdict

try:
    import fcntl
except ImportError:  # 윈도우 개발 환경. 여러 프로세스로 띄울 일이 없다.
    fcntl = None

import requests

from stelline.config import PROJECT_ROOT, SEARCH_API_INTERVAL, SEARCH_API_KEY, TEMP_API_KEY
from stelline.database.connection import database_cursor
from stelline.http_client import SESSION

LAST_SEARCH_FILE = "last_search_time.txt"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# 유튜브 검색 결과 페이지에 박혀 있는 JSON 덩어리. 크롤링마다 다시 만들 이유가 없다.
YT_INITIAL_DATA_RE = re.compile(r"ytInitialData\s*=\s*({.*?});", re.DOTALL)

# 위험도 값의 범위(1..28). 값이 큰 쪽부터 먼저 검사한다.
MAX_RISK = 28

# 한 회차에 부를 수 있는 YouTube 검색 횟수. 세 회차 × 30 = 하루 9,000 이라 할당량 10,000 중
# 1,000 을 같은 프로젝트의 다른 사용분 몫으로 남긴다(config.SEARCH_API_INTERVAL 참고).
SEARCH_CALLS_PER_RUN = 30

# 한 회차에 위험도 높은 곡으로 채울 수 있는 최대 곡 수.
SEARCH_TARGET_LIMIT = 12


def read_last_search_timestamp():
    try:
        if not os.path.exists(LAST_SEARCH_FILE):
            with open(LAST_SEARCH_FILE, "w", encoding="utf-8") as file:
                file.write("0")
            return 0

        with open(LAST_SEARCH_FILE, "r", encoding="utf-8") as file:
            return float(file.read().strip())
    except (OSError, ValueError):
        # 파일이 비었거나 깨져 있어도 앱이 뜨지 못하는 일은 없어야 한다.
        logging.error("마지막 검색 시간 불러오기 실패")
        return 0


def write_last_search_timestamp(timestamp):
    """임시 파일에 쓴 뒤 바꿔치기한다. 쓰는 도중에 죽어도 원본이 깨지지 않는다."""
    temporary = LAST_SEARCH_FILE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        file.write(str(timestamp))
    os.replace(temporary, LAST_SEARCH_FILE)


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
    response = SESSION.get(YOUTUBE_SEARCH_URL, params=params, timeout=10)
    response.raise_for_status()
    items = response.json().get("items", [])
    return [item["id"]["videoId"] for item in items if "id" in item]


def _resolve_match(query, video_id, video_ids, song_risk):
    """영상이 검색 결과에 있으면 risk를 낮추고 True, 없으면 28로 올리고 False를 반환한다."""
    if video_id in video_ids:
        update_song_risk(query, max(song_risk - 1, 0))
        return True
    update_song_risk(query, MAX_RISK)
    return False


def crawl_search_results_for_missing_videos(songs):
    """검색 결과에 여전히 없는 곡만 돌려준다. 크롤링이 막히면 받은 목록을 그대로 돌려준다."""
    not_searched = []
    base_url = "https://www.youtube.com/results"
    headers = {"User-Agent": "Mozilla/5.0"}

    for case in songs:
        time.sleep(random.uniform(3, 8))
        query = case["query"]
        params = {"search_query": query}
        video_id = case["video_id"]
        try:
            response = SESSION.get(base_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            match = YT_INITIAL_DATA_RE.search(response.text)
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
            return songs

    return not_searched


def select_search_targets(song_infos):
    """이번 회차에 검사할 곡을 고른다.

    위험도가 높은 곡부터 최대 12곡까지 채우고, 남는 할당량은 위험도 0인 곡으로 채운다.
    반환값은 (위험도 0인 곡, 우선 검사 대상)이다.

    예전에는 위험도 1~28을 각각 전체 목록에서 훑어 스물여덟 번을 돌았다.
    한 번만 훑어 위험도별로 담아 두면 고르는 순서는 그대로면서 훨씬 싸다.
    """
    by_risk = defaultdict(list)
    for info in song_infos:
        by_risk[info.get("risk")].append(info)

    search_targets = []
    for risk_level in reversed(range(1, MAX_RISK + 1)):
        search_targets.extend(by_risk.get(risk_level, ()))
        if len(search_targets) >= SEARCH_TARGET_LIMIT:
            search_targets = search_targets[:SEARCH_TARGET_LIMIT]
            break

    return list(by_risk.get(0, ())), search_targets


def search_unverified_songs(by_admin=False):
    is_quota_exceeded = False

    song_infos = fetch_song_infos_from_db()
    logging.info("검색 시작")
    not_searched = []
    risk_zero_songs, search_targets = select_search_targets(song_infos)

    remaining_quotes = SEARCH_CALLS_PER_RUN

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
        if search_targets:
            song = search_targets.pop(0)
        elif risk_zero_songs:
            song = risk_zero_songs.pop(random.randrange(len(risk_zero_songs)))
        else:
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

    not_searched = crawl_search_results_for_missing_videos(not_searched)
    logging.info("[최종 결과] 총 실패곡=%s", len(not_searched))

    return {"all_songs": not_searched, "searched_time": time.time(), "isQuotaExceeded": is_quota_exceeded}


# 검사 한 회차는 API 할당량을 수십 번 쓰고 songs_data 를 비웠다가 다시 채운다.
# 정기 검사와 관리자 즉시 검사가 겹치면 할당량을 두 번 쓰고 결과도 서로 덮어쓰므로,
# 한 번에 한 회차만 돌게 막는다.
#
# 정기 검사는 백그라운드 작업을 맡은 워커 하나에서 돌지만, 관리자 요청은 gunicorn 의
# 어느 워커에나 떨어진다. 그래서 같은 프로세스 안의 스레드 잠금(SEARCH_LOCK)에 더해
# 프로세스끼리 통하는 파일 잠금(SEARCH_LOCK_PATH)을 함께 잡는다.
SEARCH_LOCK = threading.Lock()
SEARCH_LOCK_PATH = PROJECT_ROOT / ".search_cycle.lock"

# 파일 잠금은 파일이 열려 있는 동안만 유지된다. SEARCH_LOCK 을 쥔 스레드만 건드린다.
_search_lock_handle = None


def acquire_search_lock(blocking=True):
    """검사 한 회차를 돌려도 되면 True. blocking=False 면 누가 돌고 있을 때 바로 False."""
    global _search_lock_handle
    if not SEARCH_LOCK.acquire(blocking=blocking):
        return False
    if fcntl is None:
        return True
    try:
        handle = open(SEARCH_LOCK_PATH, "a", encoding="utf-8")
    except OSError:
        # 잠금 파일을 못 만든다고 검사를 통째로 멈추면 그쪽이 더 큰 손해다.
        logging.warning("검색 잠금 파일을 열 수 없어 프로세스 간 잠금 없이 돌립니다: %s", SEARCH_LOCK_PATH)
        return True
    try:
        fcntl.flock(handle, fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        SEARCH_LOCK.release()
        return False
    _search_lock_handle = handle
    return True


def release_search_lock():
    global _search_lock_handle
    handle, _search_lock_handle = _search_lock_handle, None
    if handle is not None:
        handle.close()  # 닫으면 파일 잠금도 풀린다.
    SEARCH_LOCK.release()


def run_search_once(by_admin=False):
    """검사 한 회차를 돌고 결과를 저장한다. 호출하는 쪽이 acquire_search_lock() 을 잡고 있어야 한다."""
    global last_search_timestamp

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


# 주기적으로 검색 데이터 가져오기
def run_search_cycle():
    logging.info("주기적 검색 시작됨")
    while True:
        acquire_search_lock()
        try:
            run_search_once()
        finally:
            release_search_lock()
        wait_until_next_search_interval()


def start_admin_search():
    """관리자 즉시 검사를 띄운다. 이미 한 회차가 돌고 있으면 띄우지 않고 False 를 돌려준다."""
    if not acquire_search_lock(blocking=False):
        return False

    def run():
        try:
            run_search_once(by_admin=True)
        finally:
            release_search_lock()

    threading.Thread(target=run, daemon=True, name="admin-search").start()
    return True


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


def start_search_scheduler():
    """다음 검색 주기가 시작될 때까지 기다렸다가 반복 검색을 시작한다."""
    logging.info("검색 스케줄러 초기화 시작")
    delay = max(5, SEARCH_API_INTERVAL - time.time() % SEARCH_API_INTERVAL)
    hours, remainder = divmod(int(delay), 3600)
    minutes, seconds = divmod(remainder, 60)
    logging.info("첫 검색을 %d:%02d:%02d 만큼 지연..", hours, minutes, seconds)
    threading.Thread(target=start_delayed_search, daemon=True, args=(delay,)).start()
