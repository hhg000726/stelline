import os

from stelline import app
from stelline.background_tasks import start_background_tasks_if_enabled
from stelline.config import DEBUG_MODE, HOST, PORT, RELOADER_MODE

if __name__ == "__main__":
    # 리로더를 켜면 감시용 부모와 실제 서버인 자식이 이 파일을 한 번씩 실행한다.
    # 작업은 요청을 받는 자식에서만 돌린다(WERKZEUG_RUN_MAIN 은 자식에만 붙는다).
    if not RELOADER_MODE or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_background_tasks_if_enabled()
    app.run(host=HOST, port=PORT, debug=DEBUG_MODE, use_reloader=RELOADER_MODE)
