from flask import Blueprint
from stelline.apis.newOne import newOne_bp
from stelline.apis.search import search_bp
from stelline.apis.bugs import bugs_bp
from stelline.apis.main import main_bp
from stelline.apis.congratulation import congratulation_bp
from stelline.apis.offline import offline_bp

api_bp = Blueprint("api", __name__)

# 각각의 앱 API 블루프린트 등록
api_bp.register_blueprint(newOne_bp, url_prefix="/newOne")
api_bp.register_blueprint(search_bp, url_prefix="/search")
api_bp.register_blueprint(bugs_bp, url_prefix="/bugs")
api_bp.register_blueprint(main_bp, url_prefix="/main")
api_bp.register_blueprint(congratulation_bp, url_prefix="/congratulation")
api_bp.register_blueprint(offline_bp, url_prefix="/offline")