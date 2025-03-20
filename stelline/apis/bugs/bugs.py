from flask import jsonify
import threading

from .bugs_api import bugs_api_process

recent_data = {}

def rank():
    return jsonify(recent_data)

threading.Thread(target = bugs_api_process, daemon=True, args = (recent_data, )).start()