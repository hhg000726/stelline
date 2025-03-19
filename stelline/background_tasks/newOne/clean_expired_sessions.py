import logging, time

from stelline.config import SESSION_CHECK_INTERVAL

# 주기적으로 세션 정리
def clean_expired_sessions_process(game_sessions):
    while True:
        logging.info("세션 만료 확인 중")
        expired_users = []
        for user, session in game_sessions.items():
            if session["last_request"] + 300 <= time.time():
                expired_users.append(user)

        for user in expired_users:
            del game_sessions[user]
            logging.info(f"{user}의 세션 만료됨, 남은 유저: {len(game_sessions)}")
        time.sleep(SESSION_CHECK_INTERVAL)