# 리눅스 전용 테스트(파일 잠금 fcntl·gunicorn)까지 포함해 전체 테스트를 도는 일회용 이미지.
#
# 윈도우에서는 그 테스트들이 건너뛰어져, 지금까지는 CI(ubuntu)에서만 돌았다.
# 운영 서버(Ubuntu 24.04)·CI 와 같은 Python 3.12 를 쓴다.
# 실행은 dev/run-linux-tests.ps1 (또는 README_DEV 의 docker compose 명령)로 한다.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 의존성만 먼저 설치해 둔다. requirements 가 그대로면 다음 실행에서는 이 단계를 다시 하지 않는다.
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

# 지금 작업 폴더를 그대로 복사한다(커밋하지 않은 수정도 포함). 무엇을 빼는지는 .dockerignore 가 정한다.
# 폴더를 연결(마운트)하지 않고 복사하는 것은, 윈도우 폴더를 연결하면 파일 잠금이 리눅스와 다르게
# 동작할 수 있고 테스트가 만든 파일이 작업 폴더에 남기 때문이다.
COPY . .
