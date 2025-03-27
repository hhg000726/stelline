from . import search_bp
from .search import *

@search_bp.route("/not_searched", methods=["GET"])
def get_not_searched_api():
    return get_not_searched()

@search_bp.route("/record", methods=["GET"])
def record_search_api():
    return record_search()

@search_bp.route("/songs", methods=["GET"])
def get_song_infos_api():
    return get_song_infos()