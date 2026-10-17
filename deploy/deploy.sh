# 운영 서버의 ~/deploy.sh 원본. GitHub Actions 가 main 배포 때 `bash ~/deploy.sh` 로 부른다.
# 서버에서만 고치지 말고 여기도 함께 고친다.
#
# 준비 단계(pull·설치·마이그레이션) 중 하나라도 실패하면 재시작 전에 멈춘다.
# 그대로 재시작하면 새 코드가 적용되지 않은 스키마 위에서 돌면서 배포는 초록으로 끝난다.
# 멈추면 지금 떠 있는 앱은 그대로 둔 채 Actions 가 빨갛게 끝난다.
set -eo pipefail
trap 'echo "배포 중단: ${BASH_COMMAND} 가 실패했습니다. 앱은 재시작하지 않았습니다." >&2' ERR

cd stelline

# 1. 최신 코드 가져오기
git pull origin main

# 2. 가상환경 활성화 및 라이브러리 업데이트 (필요 시)
source venv/bin/activate
pip install -r requirements.txt

# DB 스키마 및 새 마이그레이션 적용
python -m stelline.database.migrate

# 3. Gunicorn 재시작 (Nginx 설정은 GitHub Actions 가 배포 때 따로 설치·reload 한다)
# systemd(stelline.service)가 띄우고, 죽거나 재부팅돼도 다시 띄운다.
sudo systemctl restart stelline

# 다시 뜨지 못했으면 배포를 실패로 끝내 Actions 에서 바로 보이게 한다.
for _ in $(seq 1 15); do
  if curl -fsS -o /dev/null http://127.0.0.1:5000/; then
    echo "stelline 재시작 완료"
    exit 0
  fi
  sleep 2
done
echo "stelline 이 다시 뜨지 않았습니다." >&2
sudo journalctl -u stelline -n 40 --no-pager >&2
exit 1

