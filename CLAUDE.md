# Stelline

스텔라이브 비공식 팬 사이트. Flask(`stelline/`) + React SPA(`frontend/`) + MySQL. 사용자는 한국어로 대화한다.

## 먼저 읽을 것
- `README.md`: 구조, **화면 공통 규칙**, 프론트엔드, 배포. 화면을 고치기 전에 "화면 공통 규칙"을 확인한다.
- `README_DEV.md`: 개발 DB, 개발 서버, 테스트, 변경을 올리는 방법, 운영 점검.
- 위 두 문서와 이 파일이 다르면 README 쪽이 맞다. 그때는 이 파일을 고친다.

## 꼭 지킬 것
- **`main`에 올라가면 곧바로 운영에 배포된다.** 브랜치 → PR → CI 초록 → squash 머지 순서로만 올린다. `main`에 직접 push하지 않는다.
- **`frontend/`를 고쳤으면** `cd frontend && npm run build` 후 `stelline/static/index.html`, `stelline/static/app/`를 같은 커밋에 넣는다. CI가 다시 빌드해 커밋된 것과 비교한다.
- 배색과 간격 토큰은 `stelline/static/assets/site.css` 한 곳에서 정한다. 관리자·로그인 화면도 이 파일을 쓴다.
- 스키마를 바꿨으면: 운영 반영은 `main` 배포 때 `deploy/deploy.sh` 가 `python -m stelline.database.migrate` 로 **자동으로 한다**. 데이터를 지우거나 바꾸는 마이그레이션이면 합치기 전에 백업이 필요하다고 PR 설명에 적고 사용자에게 알린다.
- 기존 기능과 화면 동작을 바꾸지 말라는 요청이 많다. 범위 밖의 변경은 제안만 한다.

## 명령 (저장소 맨 위에서 실행)
- 테스트: `python -m pytest -q`. MySQL이 없으면 `*_integration.py`, `test_migrations.py`, `test_background_tasks.py`는 skip된다. 로컬에서 통과해도 **CI 결과까지 확인**한다.
- DB 포함 테스트: `README_DEV.md`의 일회용 `mysql:8.4` 컨테이너에 `RDS_DB=stelline_test`를 쓴다. 테스트가 매번 모든 테이블을 비우므로 개발 DB(`3307`, `stelline_dev`)를 가리키지 않는다.
- 개발 서버: `APP_ENV=development START_BACKGROUND_TASKS=false python -m stelline` (기본 포트 5000, `PORT`로 변경 가능). 개발 DB가 필요하면 `docker compose -f dev/docker-compose.dev.yml up -d`.
- 화면 개발: `cd frontend && npm run dev` (5173, API는 Flask 5000으로 넘긴다).

## 함정
- `config.py`의 기본값은 `APP_ENV=production`, `START_BACKGROUND_TASKS=true`다. 환경 변수 없이 띄우면 실제 YouTube API를 부르고 FCM 알림을 보낼 수 있다. 백그라운드 작업은 사용자 확인 없이 켜지 않는다.
- 개발 모드는 리로더 때문에 python 프로세스가 둘 뜬다. 띄운 서버만 PID로 끈다. `taskkill //IM python.exe`처럼 전체 python을 죽이지 않는다(이 PC에서는 ComfyUI 같은 다른 작업도 돈다).
- 파일 잠금 같은 리눅스 전용 테스트는 Windows에서 skip되고 CI(ubuntu)에서만 돈다.
- 공개 주소는 Vercel(`stel-line.vercel.app`) 하나다. Vercel이 원본 서버(`168.107.1.195`) nginx 80번으로 보낸다. 이 서버에는 HTTPS 블록과 인증서를 두지 않는다(예전 자체 도메인은 일부러 정리했다). `deploy/nginx/stelline.conf`를 바꾸면 `tests/test_pages.py`의 nginx 검사도 확인한다.
- 운영 앱은 systemd `stelline.service`(워커 1개, `127.0.0.1:5000`)가 띄운다. 프로세스를 이름 패턴으로 죽이지 않는다(`pkill -f gunicorn`은 그 명령을 실행하는 원격 셸까지 죽인다). 다시 띄울 때는 `sudo systemctl restart stelline`.
- 백그라운드 작업은 앱을 불러올 때가 아니라 서버로 뜰 때만 시작한다(`gunicorn.conf.py`, `stelline/__main__.py`). `stelline/__init__.py`에서 작업을 시작하지 않는다.

## 커밋과 PR
- 제목은 한국어 평서형으로, 사용자가 겪는 변화를 쓴다. 예: `'마지막 갱신'을 한국 시간으로 보여 준다`. 브랜치는 `feat/`, `fix/`, `chore/`, `docs/`를 쓴다.
- 코드 주석도 한국어로, 무엇보다 **왜** 그렇게 했는지를 쓴다. 주변 코드의 말투를 따른다.
