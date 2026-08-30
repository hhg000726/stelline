from . import karaoke_bp
from .service import fetch_songs, record_copy, submit_karaoke_report


@karaoke_bp.route("/songs", methods=["GET"])
def get_songs_api():
    return fetch_songs()


@karaoke_bp.route("/reports", methods=["POST"])
def submit_karaoke_report_api():
    return submit_karaoke_report()


@karaoke_bp.route("/record_copy", methods=["POST"])
def record_copy_api():
    return record_copy()
