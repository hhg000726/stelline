from . import congratulation_bp
from .congratulation import *

@congratulation_bp.route("/congratulations", methods=["GET"])
def congratulation_api():
    return congratulations()