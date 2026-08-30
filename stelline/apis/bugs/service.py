from flask import jsonify

from .tasks import recent_rank_data


def fetch_rank_data():
    return jsonify(recent_rank_data.copy())
