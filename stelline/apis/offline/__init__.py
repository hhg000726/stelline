from flask import Blueprint

offline_bp = Blueprint("offline", __name__)

from . import routes  # `routes.py`에서 엔드포인트 등록