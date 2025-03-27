from flask import jsonify, request
from . import newOne_bp
from .game import start_game, submit_choice, get_leaderboard

@newOne_bp.route("/start_game", methods=["GET"])
def start_game_api():
    return start_game()

@newOne_bp.route("/submit_choice", methods=["POST"])
def submit_choice_api():
    return submit_choice(request.get_json())

@newOne_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard_api():
    return jsonify(get_leaderboard())