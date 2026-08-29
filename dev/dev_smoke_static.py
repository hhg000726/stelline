import requests

BASE = "http://127.0.0.1:5000"
ASSETS = [
    "/assets/site.css",
    "/assets/site.js",
    "/firebase-messaging-sw.js",
    "/search/style.css",
    "/search/search.js",
    "/search/1.PNG",
    "/search/2.PNG",
    "/search/3.PNG",
    "/search/1.jpg",
    "/search/2.jpg",
    "/search/3.jpg",
    "/search/4.jpg",
    "/congratulation/congratulation.js",
    "/congratulation/app.js",
]

for path in ASSETS:
    url = BASE + path
    try:
        r = requests.get(url, timeout=5)
        print(f"GET {path} -> {r.status_code}")
        if 'text' in r.headers.get('Content-Type',''):
            print(r.text[:200])
        else:
            print(f"(binary content, {len(r.content)} bytes)")
    except Exception as e:
        print(f"GET {path} -> ERROR: {e}")
    print('-'*40)
