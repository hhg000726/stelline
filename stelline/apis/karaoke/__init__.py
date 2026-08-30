from flask import Blueprint

karaoke_bp = Blueprint("karaoke", __name__)

from . import routes  # `routes.py`에서 엔드포인트 등록
