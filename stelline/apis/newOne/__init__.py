from flask import Blueprint

newOne_bp = Blueprint("newOne", __name__)

from . import routes  # `routes.py`에서 엔드포인트 등록