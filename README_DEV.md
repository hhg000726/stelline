Quick dev checklist — run these in separate terminals

1) Start dev server (background tasks disabled, default):

PowerShell
```
./run-development.ps1
```

2) To start server with background tasks (monitoring, search scheduler) enabled:

PowerShell
```
./run-development-with-bg.ps1
```

Note: enabling background tasks may call external APIs (YouTube, Firebase). Make sure the following env vars in `.env.development` are set if you enable background tasks:
- `API_KEY` (YouTube API key)
- `PLAYLIST_ID`
- `SERVICE_ACCOUNT_FILE` and `PROJECT_ID` for FCM

3) Smoke check endpoints (after server is running):

Python
```
python dev_smoke_checks.py
```

4) Simulate milestone crossing without sending real FCM notifications:

Python
```
python dev_test_milestone.py
```

If you want, I can change `.env.development` to enable `START_BACKGROUND_TASKS=true` automatically — confirm before I patch it.

## 테스트

```
pip install -r requirements-dev.txt
pytest
```

- 순수 단위 테스트(`test_units.py`)와 화면/정적 자원 테스트(`test_pages.py`, `test_public_api.py`)는 DB 없이 실행됩니다.
- `*_integration.py`, `test_migrations.py`, `test_background_tasks.py` 는 **실제 MySQL**이 필요합니다.
  MySQL이 없으면 자동으로 `skip` 됩니다.

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
