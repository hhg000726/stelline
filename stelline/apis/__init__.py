from flask import Blueprint
from stelline.apis.newOne import newOne_bp
from stelline.apis.search import search_bp

api_bp = Blueprint("api", __name__)

# 각각의 앱 API 블루프린트 등록
api_bp.register_blueprint(newOne_bp, url_prefix="/newOne")
api_bp.register_blueprint(search_bp, url_prefix="/search")