#!/bin/bash
# 운영 서버의 ~/db-backup.sh 원본. 서버에서만 고치지 말고 여기도 함께 고친다.
# systemd 타이머(deploy/systemd/stelline-db-backup.timer)가 매일 04:30(한국 시간)에 부른다.
#
# 왜 직접 덤프하나: 운영 DB(Oracle MySQL HeatWave, Always Free)는 자동 백업을 1일만 남기고 그 기간을
# 바꿀 수 없다. 수동 백업과 시점 복구(PITR)도 막혀 있다. 그래서 하루 넘게 지나서 알아챈 실수
# (잘못된 마이그레이션, 실수로 지운 데이터)는 되돌릴 길이 없었다. 이 서버 디스크에 날마다 덤프를 떠
# 최근 KEEP 개(하루 한 번이면 약 30일)를 남긴다. DB 와 이 서버는 따로 있는 자원이라, DB 를 잃어도 여기 남는다.
#
# - 접속 정보는 앱과 같은 ~/stelline/.env 를 systemd 가 읽어 넘긴다(EnvironmentFile).
#   비밀번호는 명령줄에 싣지 않는다(ps 로 보인다). MYSQL_PWD 환경 변수로만 넘긴다.
# - 결과를 앱 로그와 같은 모양(`시각 [수준] {스레드} 내용`)으로 한 줄 남겨 관리자 화면 '운영 로그' 탭에 보이게 한다.
#   실패하면 경고·오류 파일에도 남겨 '오류·경고'에 뜬다. 서버에 들어가지 않고도 백업이 멈춘 것을 알 수 있다.
# - 수동으로 한 번 뜨기(마이그레이션 직전 등): sudo systemctl start stelline-db-backup
#   결과는 journalctl -u stelline-db-backup 또는 '운영 로그' 탭.
# - 되살리기는 README.md 의 'DB 백업' 을 본다.
set -Eeuo pipefail

# 시험할 때는 두 폴더를 바꿔 운영 로그와 실제 백업 폴더를 건드리지 않는다.
BACKUP_DIR=${DB_BACKUP_DIR:-/home/ubuntu/backup/db}
LOG_DIR=${DB_BACKUP_LOG_DIR:-/home/ubuntu/stelline/logs}
KEEP=30

TMP=""
ERR_FILE=""
cleanup() {
  if [ -n "$TMP" ]; then rm -f "$TMP"; fi
  if [ -n "$ERR_FILE" ]; then rm -f "$ERR_FILE"; fi
}
trap cleanup EXIT

# log_line 수준 내용 파일...
# 시각은 서버 시간대와 상관없이 한국 시간이다(관리자 화면이 한국 시간으로 읽는다).
log_line() {
  local level=$1 message=$2 stamp file
  shift 2
  stamp=$(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S,000')
  for file in "$@"; do
    # 로그를 못 써도 백업 결과는 그대로 둔다. 내용은 아래 echo 로 journal 에도 남는다.
    printf '%s [%s] {db-backup} %s\n' "$stamp" "$level" "$message" >> "${LOG_DIR}/${file}" 2>/dev/null || true
  done
  echo "$message"
}

fail() {
  trap - ERR
  log_line ERROR "DB 백업 실패: $1" app_event.log app_info.log app_warning.log app_error.log >&2
  exit 1
}
# 아래에서 따로 잡지 않은 실패. BASH_COMMAND 는 변수를 펼치기 전의 글자라 비밀번호가 들어가지 않는다.
trap 'fail "${BASH_COMMAND} (줄 ${LINENO})"' ERR

for name in RDS_HOST RDS_USER RDS_PASSWORD RDS_DB; do
  if [ -z "${!name:-}" ]; then fail ".env 에 ${name} 가 없습니다"; fi
done
export MYSQL_PWD="$RDS_PASSWORD"
DB_ARGS=(--host="$RDS_HOST" --port="${RDS_PORT:-3306}" --user="$RDS_USER")

umask 077
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

NAME="stelline-$(TZ=Asia/Seoul date +%Y%m%d-%H%M%S).sql.gz"
# 끝까지 쓰고 검사를 통과한 것만 제 이름으로 바꾼다. 중간에 멈춘 파일이 백업처럼 보이지 않게 한다.
TMP="${BACKUP_DIR}/.${NAME}.partial"
ERR_FILE=$(mktemp)

# --single-transaction: 표를 잠그지 않고 한 시점의 모습을 뜬다(모두 InnoDB). 앱은 그동안 그대로 돈다.
# --set-gtid-purged=OFF: HeatWave 는 GTID 를 켜 두었다. 이 줄이 덤프에 들어가면 다른 서버(개발 DB 등)에 넣을 때 막힌다.
# --no-tablespaces: 표 공간 정보는 되살리는 데 필요 없고, 읽으려면 권한이 더 든다.
# --databases 를 쓰지 않는다. 그래야 덤프에 DB 이름이 박히지 않아 아무 이름의 DB 에나 되살릴 수 있다.
if ! mysqldump "${DB_ARGS[@]}" \
    --single-transaction --quick --routines --triggers --hex-blob \
    --set-gtid-purged=OFF --no-tablespaces --default-character-set=utf8mb4 \
    "$RDS_DB" 2>"$ERR_FILE" | gzip -6 > "$TMP"; then
  # mysqldump 의 오류 줄은 'mysqldump: ...' 로 시작하므로 앞에 더 붙이지 않는다.
  fail "$(tail -n 1 "$ERR_FILE" | tr -d '\r')"
fi

# 덤프가 정말 끝까지 쓰였는지, 표가 빠지지 않았는지 확인한다.
gzip -t "$TMP" || fail "압축 파일이 깨졌습니다"
LAST_LINE=$(zcat "$TMP" | tail -n 1)
if [[ $LAST_LINE != "-- Dump completed"* ]]; then fail "덤프가 끝까지 쓰이지 않았습니다"; fi
DUMPED=$(zcat "$TMP" | grep -c '^CREATE TABLE ' || true)
if ! EXPECTED=$(mysql "${DB_ARGS[@]}" --connect-timeout=20 -N -B -e \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'" \
    "$RDS_DB" 2>"$ERR_FILE"); then
  fail "표 수 확인: $(tail -n 1 "$ERR_FILE" | tr -d '\r')"
fi
if [ "$DUMPED" -ne "$EXPECTED" ]; then fail "표 수가 다릅니다(덤프 ${DUMPED}개, DB ${EXPECTED}개)"; fi

mv "$TMP" "${BACKUP_DIR}/${NAME}"
TMP=""

# 새 덤프가 성공한 뒤에만 오래된 것을 지운다. 날짜가 아니라 개수로 센다. 백업이 한동안 실패해도
# 날짜 기준이면 남은 것까지 다 지워지지만, 개수 기준이면 마지막 KEEP 개는 남는다.
# shellcheck disable=SC2012  # 이름에 빈칸이 없는 우리 파일만 다룬다.
ls -1t "$BACKUP_DIR"/stelline-*.sql.gz | tail -n +$((KEEP + 1)) | xargs -r rm -f --

SIZE_KB=$(( ($(stat -c %s "${BACKUP_DIR}/${NAME}") + 1023) / 1024 ))
COUNT=$(ls -1 "$BACKUP_DIR"/stelline-*.sql.gz | wc -l)
log_line INFO "DB 백업 완료: ${NAME} (표 ${DUMPED}개, ${SIZE_KB}KB), 보관 ${COUNT}개" app_event.log app_info.log
