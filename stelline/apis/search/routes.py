from . import search_bp
from .service import get_not_searched, get_search_status, get_song_infos, record_search, submit_song_report

# 즉시 검사는 관리자 화면(`/admin/search/force`)에서만 띄운다. 공개 API 로 두면 누구나
# 관리자 키의 YouTube 할당량을 써 버릴 수 있다.

# 검색 화면이 쓰는 주소. 곡별 현재 상태·최근 7일 기록을 한 번에 준다.
@search_bp.route("/status", methods=["GET"])
def get_search_status_api():
    return get_search_status()

# 아래 두 주소는 바깥에서 읽는 쪽을 위해 예전 모양 그대로 남긴다(값은 같은 판정에서 나온다).
@search_bp.route("/not_searched", methods=["GET"])
def get_not_searched_api():
    return get_not_searched()

@search_bp.route("/record", methods=["GET"])
def record_search_api():
    return record_search()

@search_bp.route("/songs", methods=["GET"])
def get_song_infos_api():
    return get_song_infos()

@search_bp.route("/reports", methods=["POST"])
def submit_song_report_api():
    return submit_song_report()
