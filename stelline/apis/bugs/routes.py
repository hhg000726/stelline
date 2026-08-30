from . import bugs_bp
from .service import fetch_rank_data


@bugs_bp.route("/rank", methods=["GET"])
def rank_api():
    return fetch_rank_data()