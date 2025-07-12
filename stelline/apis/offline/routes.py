from . import offline_bp
from .offline_api import *

@offline_bp.route("/offline_api", methods=["GET"])
def offline():
    return offline_api()