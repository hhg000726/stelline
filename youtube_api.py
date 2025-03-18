from config import *
import logging, requests

def get_songs():
    logging.info("유튜브 API에서 곡 목록을 가져오는 중...")
    URL = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={PLAYLIST_ID}&maxResults={MAX_RESULTS}&key={API_KEY}"
    songs = []
    video_ids = []
    next_page_token = None

    try:
        while True:
            try:
                response = requests.get(URL + (f"&pageToken={next_page_token}" if next_page_token else ""), timeout=10)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logging.error(f"YouTube API 요청 실패: {e}")
                return []
            
            data = response.json()
            for item in data.get("items", []):
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_ids.append(video_id)
                songs.append({
                    "title": item["snippet"]["title"],
                    "video_id": video_id
                })

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

        logging.info(f"{len(songs)}개의 곡을 가져왔습니다.")

        for i in range(0, len(video_ids), MAX_RESULTS):
            video_id_str = ",".join(video_ids[i:i + MAX_RESULTS])
            video_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id_str}&key={API_KEY}"
            video_response = requests.get(video_url).json()

            for item in video_response.get("items", []):
                video_id = item["id"]
                published_at = item["snippet"]["publishedAt"]

                for song in songs:
                    if song["video_id"] == video_id:
                        song["date"] = published_at

        return songs
    except Exception as e:
        logging.error(f"YouTube API에서 곡을 가져오는 중 오류 발생: {e}")
        return []