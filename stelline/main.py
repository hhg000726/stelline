import logging
from stelline import app
from stelline.config import *
from stelline.database.db_migration import *

if __name__ == "__main__":
    logging.info("서버 시작됨")
    check_migration()
    app.run(host=HOST, port=PORT, debug=DEBUG_MODE, use_reloader=RELOADER_MODE)