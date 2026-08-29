from . import search_bp
from .search import force_search_now, get_not_searched, get_song_infos, record_search, submit_song_report

@search_bp.route("/force_search", methods=["GET"])
def force_search_now_api():
    return force_search_now()

@search_bp.route("/not_searched", methods=["GET"])
def get_not_searched_api():
    return get_not_searched()

@search_bp.route("/record", methods=["GET"])
def record_search_api():
    return record_search()

@search_bp.route("/songs", methods=["GET"])
def get_song_infos_api():
    return get_song_infos()

@search_bp.route("/reports", methods=["POST"])
def submit_song_report_api():
    return submit_song_report()
