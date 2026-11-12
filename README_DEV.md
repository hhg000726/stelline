Quick dev checklist — 모든 명령은 **저장소 맨 위 폴더**에서 실행합니다(`python -m stelline` 이 그 위치를 기준으로 찾습니다).

0) 처음 한 번 — 개발 DB와 설정 파일:

PowerShell
```
Copy-Item dev/.env.development.example .env.development
docker compose -f dev/docker-compose.dev.yml up -d
pip install -r requirements-dev.txt
```

`.env.development` 는 맨 위 폴더에 있어야 합니다(`stelline/config.py` 가 거기서 읽습니다). 커밋하지 않습니다.

1) 화면(React) 빌드 — 처음 한 번과, `frontend/` 를 고칠 때마다:

PowerShell
```
cd frontend
npm install
npm run build
```

빌드 결과물(`stelline/static/index.html`, `stelline/static/app/`)은 저장소에 커밋합니다.
배포 서버에는 Node 를 두지 않기 때문입니다. CI 가 다시 빌드해 커밋된 것과 같은지 확인합니다.
화면을 고치며 바로 확인하려면 `npm run dev`(5173)를 Flask 와 함께 띄우세요.

2) 개발 서버(백그라운드 작업 끔, 기본):

PowerShell
```
./dev/run-development.ps1
```

3) 백그라운드 작업(조회수 감시·검색 점검·Bugs 순위)까지 켜려면:

PowerShell
```
./dev/run-development-with-bg.ps1
```

백그라운드 작업은 실제 외부 API(YouTube, Firebase)를 부릅니다. 켜기 전에 `.env.development` 에 다음 값이 있어야 합니다.
- `API_KEY` (YouTube API key), `PLAYLIST_ID`
- `SERVICE_ACCOUNT_FILE`, `PROJECT_ID` (FCM)

**운영 구독자에게 알림이 나갈 수 있으니 운영 서비스 계정을 개발에 넣지 마세요.**

4) 서버를 띄운 뒤 주소 점검:

PowerShell
```
python dev/dev_smoke_checks.py
python dev/dev_smoke_all_apis.py
```

5) 실제 알림을 보내지 않고 조회수 달성을 흉내 내기(개발 DB 필요):

PowerShell
```
python -m dev.dev_test_milestone
```

## 테스트

```
pip install -r requirements-dev.txt
pytest
```

- 순수 단위 테스트(`test_units.py`, `test_units_refactors.py`)와 화면/정적 자원 테스트(`test_pages.py`, `test_public_api.py`)는 DB 없이 실행됩니다.
  `test_pages.py` 는 서버가 내려주는 것(주소마다 문서를 주는지, 빌드 결과물이 실제로 있는지)과
  화면 소스(`frontend/src`)가 예전 규칙을 그대로 지키는지, nginx 설정이 캐시·전달 규칙을 지키는지를 함께 봅니다.
- `*_integration.py`, `test_migrations.py`, `test_background_tasks.py` 는 **실제 MySQL**이 필요합니다.
  MySQL이 없으면 자동으로 `skip` 됩니다. 로컬에서 통과했다고 끝이 아니라 **CI 결과까지 확인**하세요.
- 파일 잠금처럼 리눅스에서만 의미 있는 테스트는 윈도우에서 `skip` 됩니다. 아래 `리눅스에서 전체 테스트`로
  로컬에서도 돌릴 수 있습니다.

### 리눅스에서 전체 테스트

파일 잠금(`fcntl`)·gunicorn 테스트까지 포함해, CI와 같은 조건(Python 3.12·MySQL 8.4·`REQUIRE_DB=1`)으로
도커 안의 리눅스에서 돌립니다. Docker Desktop 만 켜져 있으면 되고, 개발 DB나 이 PC의 다른 MySQL과
부딪히지 않습니다(호스트 포트를 열지 않는 일회용 DB를 쓰고, 끝나면 지웁니다).

PowerShell
```
./dev/run-linux-tests.ps1                 # 전체
./dev/run-linux-tests.ps1 -k background   # pytest 인자를 그대로 넘긴다
```

- 지금 작업 폴더를 이미지에 **복사**해 돌리므로 커밋하지 않은 수정도 시험합니다. 무엇을 빼는지는 `.dockerignore`.
- 처음 한 번은 이미지를 받고 의존성을 설치하느라 몇 분 걸리고, 그 뒤로는 테스트만 돌아 수십 초면 끝납니다.
- 다른 셸에서는 `docker compose -f dev/docker-compose.linux-tests.yml -p stelline-linux-tests run --rm --build tests`
  뒤에 `... down -v` 로 일회용 DB를 지웁니다.

DB 통합 테스트를 로컬에서 돌리려면 일회용 MySQL을 띄우고 접속 정보를 넘겨줍니다:

```
docker run -d --rm --name stelline-test-db -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=stelline_test -p 3306:3306 mysql:8.4
$env:RDS_HOST='127.0.0.1'; $env:RDS_PORT='3306'; $env:RDS_USER='root'; $env:RDS_PASSWORD='root'; $env:RDS_DB='stelline_test'
$env:ADMIN_USERNAME='admin'; $env:ADMIN_PASSWORD='test-admin-password'; $env:SECRET_KEY='test-secret-key'
pytest
```

> 테스트는 지정한 `RDS_DB`의 모든 테이블을 매 테스트마다 비웁니다. 개발 DB(`stelline_dev`)를 가리키지 마세요.

CI(GitHub Actions, `.github/workflows/deploy.yml`)는 MySQL 서비스 컨테이너를 띄워 전체 스위트를
실행하며, `REQUIRE_DB=1` 이라 DB가 없으면 skip 대신 즉시 실패합니다. `main` 배포는 `test` 잡이
통과해야만 진행됩니다.

## 변경을 올리는 방법

`main` 에 올라간 것은 **곧바로 운영에 배포**됩니다(nginx 설정 설치·reload 포함). 그래서:

1. 브랜치를 만들어 PR 로 올립니다. PR 에서도 같은 `test` 잡이 돕니다.
2. CI 가 초록이 된 뒤 합칩니다. `main` 에 직접 push 하면 테스트와 배포가 같은 실행에서 이어져,
   테스트가 실패해야만 배포가 멈춥니다(검토할 틈이 없습니다).
3. 화면 소스를 고쳤으면 빌드 결과물도 같은 커밋에 넣습니다.
4. 스키마를 바꿨으면, 운영에는 `main` 배포 때 `deploy/deploy.sh` 가 `python -m stelline.database.migrate` 를
   **자동으로** 실행합니다. 데이터를 지우거나 바꾸는 마이그레이션이면 합치기 전에 운영 DB를 한 번 더 덤프하고
   (서버에서 `sudo systemctl start stelline-db-backup`, README 의 `DB 백업`), PR 설명에 그렇게 적습니다.

## 운영 점검 루틴

자동으로 도는 것과 사람이 해야 하는 것을 나눠 적습니다. 자동이라고 적히지 않은 것은 아무도 대신 해 주지 않습니다.

| 언제 | 무엇을 | 자동? | 확인 기준 |
| --- | --- | --- | --- |
| 5분마다 | 조회수 감시·만료 데이터 정리 | 자동(서버 백그라운드) | 관리자 화면 `운영 로그` 탭의 `조회수 감시` 가 `정상`. 서버에서는 `logs/app_info.log` 에 `YouTube 조회수 동기화 완료` 가 5분 간격으로 찍힘 |
| 8시간마다(01·09·17시, `config.SEARCH_API_INTERVAL`) | 검색 점검 | 자동(서버 백그라운드) | `운영 로그` 탭의 `검색 점검` 이 `정상`이고 마지막 회차 요약(검사 곡 수·재시도 m/n곡·순회·API 횟수)이 보임. 로그로는 `검색 점검 완료` 또는 `쿼터 초과`. `검색 점검 곡` 표 위 요약의 '한 바퀴 도는 기간'이 계속 늘면 예산이 곡 수에 비해 모자란 것 |
| push/PR 마다 | 테스트·빌드 일치 검사·배포 | 자동(GitHub Actions) | Actions 가 초록 |
| 배포 직후 | 공개 화면 5개·관리자 로그인이 열리는지, 두 앱 서버가 떠 있는지 | 사람 | `https://stel-line.vercel.app/`, `/search`, `/karaoke`, `/congratulation`, `/offline`, `/admin/`. 서버에서 `systemctl is-active stelline stelline-standby` 가 둘 다 `active`(README 의 `핫 스탠바이`) |
| 주 1회 | `운영 로그` 탭의 오류·경고 훑기, 관리자 화면의 사용자 제보 3종 처리 | 사람 | 같은 오류가 반복되지 않음, 제보가 쌓이지 않음 |
| 매일 04:30 | 운영 DB 덤프 백업(서버의 `~/backup/db/`, 최근 30개) | 자동(systemd 타이머) | `운영 로그` 탭의 `운영 기록` 에 `DB 백업 완료` 가 날마다 한 줄. `DB 백업 실패` 가 보이면 README 의 `DB 백업` |
| 월 1회 | `npm audit`, `pip list --outdated`, 운영 DB 백업(`~/backup/db/`)이 실제로 복원되는지 | 사람 | 고위험 취약점 0, 메이저 판올림은 PR 로 따로. 덤프 하나를 일회용 MySQL 컨테이너에 넣어 오류 없이 들어가는지 |
| 오류·장애 시 | `운영 로그` 탭(또는 서버의 `app_error.log`) → 최근 배포 커밋 → 필요하면 `git revert` 로 되돌린 PR | 사람 | 되돌린 뒤 위 "배포 직후" 점검 통과 |

### 로그

서버의 실행 폴더 아래 `logs/` 에 쌓입니다(`stelline/logging_config.py`). 관리자 화면의 **운영 로그** 탭이
이 파일들을 읽어 요약하므로(`stelline/admin/server_logs.py`), 평소에는 서버에 들어가지 않아도 됩니다.

| 파일 | 담는 것 |
| --- | --- |
| `app_info.log` | INFO 이상 전부. 백그라운드 작업이 무엇을 했는지가 여기 있습니다 |
| `app_warning.log` | WARNING 이상. `운영 로그` 탭의 `오류·경고` 가 읽습니다 |
| `app_error.log` | ERROR 이상 |
| `app_event.log` | 운영 기록만(검색 점검 결과, 관리자 작업, 조회수 달성 알림, 사용자 제보, 서버 시작, DB 백업). `운영 로그` 탭의 `운영 기록` 이 읽습니다 |

- 한 줄은 `2026-10-24 09:00:20,010 [INFO] {search} 내용` 모양입니다. `{}` 안은 그 줄을 남긴 스레드이고
  (`monitoring`·`search`·`admin-search`·`bugs-rank`, 요청 처리는 `MainThread`), 시각은 서버 시간대와 상관없이 한국 시간입니다.
- `{db-backup}` 줄만은 앱이 아니라 DB 백업 스크립트(`deploy/db-backup.sh`)가 같은 모양으로 직접 덧붙입니다. 성공은
  `app_event.log`·`app_info.log` 에, 실패는 경고·오류 파일까지 남깁니다(README 의 `DB 백업`).
- 자정마다 새 파일로 넘어가고, **7일이 지난 것은 날짜로 지웁니다.** 경고·오류 파일처럼 가끔만 쓰이는 파일도
  마지막으로 쓴 지 7일이 지나면 비웁니다(예전에는 개수로 지워서, 몇 주 전 오류 로그까지 남았습니다).
- **API 키는 파일에 쓰기 직전에 가립니다**(`key=<가림>`). 외부 API 오류는 요청 주소 대신 상태 코드와 사유만
  남깁니다. 예) `HTTP 403 quotaExceeded (www.googleapis.com): …`(`stelline/http_client.py` 의 `describe_request_error`).
- 화면을 열 때마다 생기는 요청 기록은 DEBUG 라 파일에 남지 않습니다. 요청이 들어왔다는 사실은 nginx 접속 로그에 있습니다.
- 운영자가 알아야 할 일을 새로 남기려면 `from stelline.logging_config import events` 로 `events.info(...)`
  (문제가 있으면 `events.warning(...)`)를 씁니다. 요청마다 생기는 일에는 쓰지 마세요. 정작 봐야 할 기록이 묻힙니다.
- 테스트는 환경 변수 `LOG_DIR` 로 임시 폴더를 넘겨, 개발 폴더의 `logs/` 를 건드리지 않습니다(`tests/conftest.py`).
