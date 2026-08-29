# Stelline 개발 환경

## 구조

- `stelline/static/`: 공개 화면의 HTML·기능별 JavaScript·공통 `assets/` 디자인/API 도우미입니다. 공개 화면은 모두 이 방식으로 제공됩니다.
- `stelline/templates/`: 로그인 및 관리자처럼 서버 세션과 보호된 데이터를 즉시 렌더링해야 하는 화면입니다.
- `stelline/apis/`: 기능별 HTTP API입니다. 각 `routes.py`는 라우트만, 나머지 모듈은 기능 로직을 담당합니다.
- `stelline/database/`: 연결 생성, 코드 기준 스키마, 마이그레이션입니다.
- `stelline/background_tasks/`: 운영에서만 시작되는 YouTube·검색·Bugs 동기화 작업입니다.

## 환경 분리

- 운영은 `.env`와 운영 RDS를 사용합니다. 운영 DB에 자동으로 스키마를 적용하지 않습니다.
- 개발은 `.env.development`와 Docker의 `stelline_dev` MySQL을 사용합니다. 개발 기본값은 외부 API 호출과 FCM 발송을 비활성화합니다.

## 개발 시작

1. `docker compose -f docker-compose.dev.yml up -d`로 개발 DB를 시작합니다.
2. `pip install -r requirements.txt` 후 `./run-development.ps1`을 실행합니다.
3. `AUTO_CREATE_SCHEMA=true`이면 코드 기준 스키마가 빈 개발 DB에 자동 생성됩니다.

## 스키마 변경

스키마는 `stelline/database/schema.py`의 `MIGRATIONS`가 기준입니다. 새 변경은 새 버전의 migration을 추가하고, 개발 DB에서는 앱을 재시작하거나 `python -m stelline.database.migrate`로 적용합니다. 운영 배포 시에는 백업 후 이 명령을 명시적으로 실행하세요.

운영에서 `AUTO_CREATE_SCHEMA`는 항상 `false`로 유지하세요.

## 관리자 HTML로 개발 데이터 채우기

운영 관리자 페이지에서 저장한 HTML 파일은 개발 DB의 데이터 스냅샷으로 사용할 수 있습니다. 이는 역마이그레이션이 아니라 개발용 시드 데이터 import입니다.

```powershell
$env:APP_ENV = 'development'
python -m stelline.database.import_admin_html "C:\path\관리자 페이지.html" --dry-run
python -m stelline.database.import_admin_html "C:\path\관리자 페이지.html" --replace
```

`--replace`는 HTML에 포함된 개발 테이블 데이터를 비운 뒤 해당 스냅샷으로 바꿉니다. 개발 환경에서만 실행되며, 운영 FCM 토큰과 제거된 게임 리더보드는 가져오지 않습니다.
