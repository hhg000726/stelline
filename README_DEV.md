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
- 파일 잠금처럼 리눅스에서만 의미 있는 테스트는 윈도우에서 `skip` 되고 CI(ubuntu)에서 돕니다.

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
4. 스키마를 바꿨으면 운영 DB 백업 → `python -m stelline.database.migrate` 를 **직접** 실행합니다(자동 적용 안 됨).

## 운영 점검 루틴

자동으로 도는 것과 사람이 해야 하는 것을 나눠 적습니다. 자동이라고 적히지 않은 것은 아무도 대신 해 주지 않습니다.

| 언제 | 무엇을 | 자동? | 확인 기준 |
| --- | --- | --- | --- |
| 5분마다 | 조회수 감시·만료 데이터 정리 | 자동(서버 백그라운드) | `logs/app_info.log` 에 `YouTube 조회수 동기화 완료` 가 5분 간격으로 찍힘 |
| 6시간마다 | 검색 점검 | 자동(서버 백그라운드) | `검색 데이터 업데이트 완료!` 또는 `쿼터 초과` |
| push/PR 마다 | 테스트·빌드 일치 검사·배포 | 자동(GitHub Actions) | Actions 가 초록 |
| 배포 직후 | 공개 화면 5개·관리자 로그인이 열리는지 | 사람 | `https://stelline.xyz/`, `/search`, `/karaoke`, `/congratulation`, `/offline`, `/admin/` |
| 주 1회 | `logs/app_error.log` 훑기, 관리자 화면의 사용자 제보 3종 처리 | 사람 | 같은 오류가 반복되지 않음, 제보가 쌓이지 않음 |
| 월 1회 | `npm audit`, `pip list --outdated`, 운영 DB 백업이 실제로 복원되는지 | 사람 | 고위험 취약점 0, 메이저 판올림은 PR 로 따로 |
| 오류·장애 시 | `app_error.log` → 최근 배포 커밋 → 필요하면 `git revert` 로 되돌린 PR | 사람 | 되돌린 뒤 위 "배포 직후" 점검 통과 |

로그는 서버의 실행 폴더 아래 `logs/` 에 수준별로 쌓이고 7일 뒤 지워집니다.
