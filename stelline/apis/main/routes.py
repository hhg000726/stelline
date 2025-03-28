from . import main_bp
from .main import *

@main_bp.route("/record", methods=["GET"])
def record_main_api():
    return record_main()

@main_bp.route("/events", methods=["GET"])
def get_events_api():
    return get_events()

@main_bp.route("/twits", methods=["GET"])
def get_twits_api():
    return get_twits()