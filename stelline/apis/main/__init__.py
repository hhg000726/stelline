from flask import Blueprint

main_bp = Blueprint("main", __name__)

from . import routes  # `routes.py`에서 엔드포인트 등록