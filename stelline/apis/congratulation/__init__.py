from flask import Blueprint

congratulation_bp = Blueprint("congratulation", __name__)

from . import routes  # `routes.py`에서 엔드포인트 등록