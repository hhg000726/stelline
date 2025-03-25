from . import main_bp
from .main import *

@main_bp.route("/record", methods=["GET"])
def record_main_api():
    return record_main()