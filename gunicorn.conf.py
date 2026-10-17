"""운영 gunicorn 설정.

gunicorn 은 작업 폴더의 gunicorn.conf.py 를 따로 지정하지 않아도 읽는다.
systemd(deploy/systemd/stelline.service)의 WorkingDirectory 가 저장소 맨 위라 이 파일이 쓰인다.
"""


def post_worker_init(worker):
    """워커가 앱을 불러온 직후, 그 워커에서 백그라운드 작업을 시작한다.

    앱을 불러올 때 시작하면 마이그레이션·시드 명령처럼 앱을 잠깐 불러오기만 하는
    프로세스도 작업과 잠금(.background_tasks.lock)을 잡는다. 그 프로세스가 살아 있는 동안
    서버가 뜨면, 서버 워커는 잠금을 못 잡아 작업을 아예 건너뛴다.
    """
    from stelline.background_tasks import start_background_tasks_if_enabled

    start_background_tasks_if_enabled()
