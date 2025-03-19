from flask import jsonify
import threading

from . import search_api
from stelline.config import *

songs = {}
search_api.load_song_infos(SONG_INFOS_FILE)

def get_not_searched():
    return jsonify(songs)

threading.Thread(target = search_api.search_api_process, daemon=True, args = (songs, )).start()