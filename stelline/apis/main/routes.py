from . import search_bp
from .main import *

@search_bp.route("/record", methods=["GET"])
def record_main_api():
    return record_main()