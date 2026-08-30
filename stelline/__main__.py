from stelline import app
from stelline.config import DEBUG_MODE, HOST, PORT, RELOADER_MODE

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG_MODE, use_reloader=RELOADER_MODE)
