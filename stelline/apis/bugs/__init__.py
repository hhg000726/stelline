from flask import Blueprint

bugs_bp = Blueprint("bugs", __name__)

from . import routes  # `routes.py`에서 엔드포인트 등록