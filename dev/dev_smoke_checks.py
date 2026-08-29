import requests

BASE = "http://127.0.0.1:5000"
ENDPOINTS = [
    "/search",
    "/api/search/not_searched",
    "/api/search/songs",
    "/api/congratulation/congratulations",
]

for ep in ENDPOINTS:
    url = BASE + ep
    try:
        r = requests.get(url, timeout=5)
        print(ep, r.status_code)
        try:
            print(r.text[:400])
        except Exception:
            pass
    except Exception as e:
        print(ep, "ERROR", e)
