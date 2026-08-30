from . import offline_bp
from .service import fetch_offline_events


@offline_bp.route("/offline_api", methods=["GET"])
def offline():
    return fetch_offline_events()
