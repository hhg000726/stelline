from flask import jsonify, request
from . import bugs_bp
from .bugs import rank

@bugs_bp.route("/rank", methods=["GET"])
def rank_api():
    return rank()