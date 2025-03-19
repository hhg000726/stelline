from . import search_bp
from .search import get_not_searched

@search_bp.route("/not_searched", methods=["GET"])
def get_not_searched_api():
    return get_not_searched()