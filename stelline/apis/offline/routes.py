from . import offline_bp
from .offline_api import *

@offline_bp.route("/offline_api", methods=["GET"])
def offline_api():
    return offline_api()