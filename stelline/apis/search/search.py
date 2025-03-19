from flask import jsonify
import threading, time

from . import search_api
from stelline.config import *

songs = {}
recent = {}
search_api.load_song_infos(SONG_INFOS_FILE)

def get_not_searched():
    new_songs = songs["all_songs"]
    now = songs["searched_time"]
    for song in new_songs:
        recent[song["query"]] = [song["video_id"], now]
    for song in list(recent.keys()):
        if recent[song][1] + 604800 < time.time():
            del recent[song]
    return jsonify({"all_songs": new_songs, "searched_time": now, "recent": recent})

threading.Thread(target = search_api.search_api_process, daemon=True, args = (songs, )).start()