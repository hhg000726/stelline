from flask import Blueprint

content_bp = Blueprint("content", __name__)

from . import routes  # `routes.py`에서 엔드포인트 등록
