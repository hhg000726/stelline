# 리눅스 전용 테스트(파일 잠금·gunicorn)까지 포함해 전체 테스트를 도커 안의 리눅스에서 돌린다.
# CI(ubuntu·Python 3.12·MySQL 8.4)와 같은 조건이다. Docker Desktop 이 켜져 있어야 한다.
#
#   ./dev/run-linux-tests.ps1                 # 전체
#   ./dev/run-linux-tests.ps1 -k background   # pytest 인자를 그대로 넘긴다
#
# 저장소 맨 위 폴더에서 실행한다. 지금 작업 폴더를 그대로 복사해 돌리므로 커밋하지 않은 수정도 시험한다.
$compose = @('compose', '-f', 'dev/docker-compose.linux-tests.yml', '-p', 'stelline-linux-tests')
# 반드시 배열로 둔다. if 식의 결과로 받으면 인자 하나가 문자열이 되어, 펼칠 때 '-ra' 가
# '-', 'r', 'a' 세 글자로 쪼개져 넘어간다(PowerShell 5.1).
$testArgs = @($args)
if ($testArgs.Count -eq 0) { $testArgs = @('-ra') }

docker @compose run --rm --build tests @testArgs
$code = $LASTEXITCODE

# 일회용 DB 를 지운다. 테스트가 실패해도 지운다.
docker @compose down -v --remove-orphans 2>$null | Out-Null
exit $code
