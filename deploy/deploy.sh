# 운영 서버의 ~/deploy.sh 원본. GitHub Actions 가 main 배포 때 `bash ~/deploy.sh` 로 부른다.
# 서버에서만 고치지 말고 여기도 함께 고친다.
#
# 준비 단계(pull·설치·마이그레이션) 중 하나라도 실패하면 재시작 전에 멈춘다.
# 그대로 재시작하면 새 코드가 적용되지 않은 스키마 위에서 돌면서 배포는 초록으로 끝난다.
# 멈추면 지금 떠 있는 앱은 그대로 둔 채 Actions 가 빨갛게 끝난다.
set -eo pipefail
STAGE="준비(앱은 재시작하지 않음)"
trap 'echo "배포 중단 [${STAGE}]: ${BASH_COMMAND} 가 실패했습니다." >&2' ERR

cd stelline

# 1. 최신 코드 가져오기
git pull origin main

# 2. 가상환경 활성화 및 라이브러리 업데이트 (필요 시)
source venv/bin/activate
pip install -r requirements.txt

# DB 스키마 및 새 마이그레이션 적용
python -m stelline.database.migrate

# 다시 띄운 서버가 응답할 때까지 기다린다. 끝내 응답이 없으면 실패로 끝내 Actions 에서 바로 보이게 한다.
wait_until_up() {
  local unit=$1 port=$2
  for _ in $(seq 1 15); do
    if curl -fsS -o /dev/null "http://127.0.0.1:${port}/"; then
      echo "${unit} 재시작 완료(${port})"
      return 0
    fi
    sleep 2
  done
  echo "${unit} 이 다시 뜨지 않았습니다." >&2
  sudo journalctl -u "${unit}" -n 40 --no-pager >&2
  return 1
}

# 3. Gunicorn 재시작 (Nginx 설정은 GitHub Actions 가 배포 때 따로 설치·reload 한다)
# systemd(stelline.service)가 띄우고, 죽거나 재부팅돼도 다시 띄운다.
if systemctl cat stelline-standby.service >/dev/null 2>&1; then
  # 대기 서버(핫 스탠바이, 5001)가 있으면 한 대씩 다시 띄워 끊김 없이 바꾼다.
  # ① 대기 서버를 새 코드로 먼저 띄워 확인한다. 이 동안 요청은 그대로 본 서버가 받는다.
  #    새 코드가 뜨지 않으면 여기서 멈추고, 본 서버는 손대지 않아 옛 코드로 계속 받는다.
  STAGE="대기 서버 재시작(본 서버는 그대로)"
  sudo systemctl restart stelline-standby
  wait_until_up stelline-standby 5001
  # ② 본 서버를 다시 띄운다. 내려가 있는 몇 초 동안 nginx 가 연결 거절을 보고 요청을 대기 서버로 넘기고,
  #    본 서버가 뜨면 다시 본 서버로 돌아온다(deploy/nginx/stelline.conf 의 upstream).
  STAGE="본 서버 재시작(요청은 대기 서버가 받는 중)"
  sudo systemctl restart stelline
  wait_until_up stelline 5000
else
  # 대기 서버를 설치하기 전에는 예전처럼 본 서버만 다시 띄운다(그동안 몇 초 끊긴다).
  STAGE="본 서버 재시작"
  sudo systemctl restart stelline
  wait_until_up stelline 5000
fi
