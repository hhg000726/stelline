import requests

BASE = "http://127.0.0.1:5000"
# 공개 화면은 React 한 벌(SPA)이라, 화면별 .js/.css 는 빌드된 /app 아래로 들어갔다.
# 그 주소는 빌드마다 바뀌므로 문서에서 읽어 확인한다(아래 dev_check_pages.py 가 한다).
# 여기서는 빌드와 무관하게 늘 같은 자리에 있어야 하는 것만 본다.
ASSETS = [
    # 서버가 그리는 관리자·로그인 화면이 함께 쓰는 공용 배색과 다크 모드
    "/assets/site.css",
    "/assets/theme.js",
    "/firebase-messaging-sw.js",
    "/search/1.PNG",
    "/search/2.PNG",
    "/search/3.PNG",
    "/search/1.jpg",
    "/search/2.jpg",
    "/search/3.jpg",
    "/search/4.jpg",
    "/favicon.svg",
    "/og-image.png",
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
