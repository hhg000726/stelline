from flask import Blueprint

search_bp = Blueprint("search", __name__)

from . import routes  # `routes.py`에서 엔드포인트 등록