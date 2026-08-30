from . import main_bp
from .service import fetch_events, fetch_twits, increment_main_page_visits


@main_bp.route("/record", methods=["GET"])
def record_main_api():
    return increment_main_page_visits()


@main_bp.route("/events", methods=["GET"])
def get_events_api():
    return fetch_events()


@main_bp.route("/twits", methods=["GET"])
def get_twits_api():
    return fetch_twits()
