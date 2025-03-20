import logging
from stelline import app
from stelline.config import *

if __name__ == "__main__":
    logging.info("서버 시작됨")
    app.run(host=HOST, port=PORT, debug=DEBUG_MODE, use_reloader=RELOADER_MODE)