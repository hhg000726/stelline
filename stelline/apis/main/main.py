import json, logging

from stelline.config import *

# record 로드
def load_record():
    if os.path.exists(RECORD_MAIN):
        try:
            with open(RECORD_MAIN, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logging.error("RECORD_MAIN 불러오기 실패. 기본값으로 설정")
    return {"copy_count": 0}

# record 저장
def save_record(record):
    try:
        temp_file = RECORD_MAIN + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, RECORD_MAIN)
    except Exception as e:
        logging.error(f"RECORD_MAIN 저장 오류: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

def record_main():
    record = load_record()
    record["copy_count"] += 1  # 플레이 횟수 증가
    save_record(record)  # 저장
    
    return '', 204