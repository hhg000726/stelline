import requests
import re

BASE = "http://127.0.0.1:5000"
PAGES = ["/", "/search", "/congratulation", "/offline"]
TIMEOUT = 5

attr_re = re.compile(r'(?:src|href)=["\']([^"\']+)["\']', re.IGNORECASE)

for page in PAGES:
    url = BASE + page
    try:
        r = requests.get(url, timeout=TIMEOUT)
        print(f"PAGE {page} -> {r.status_code}")
        if r.status_code != 200:
            print(r.text[:400])
            print('-'*60)
            continue
        html = r.text
        assets = set(attr_re.findall(html))
        print(f"Found {len(assets)} assets in {page}")
        for a in sorted(assets):
            # normalize relative URLs
            if a.startswith('/'):
                asset_url = BASE + a
            elif a.startswith('http://') or a.startswith('https://'):
                asset_url = a
            else:
                # relative
                prefix = page if page.endswith('/') else page + '/'
                asset_url = BASE + prefix + a
            try:
                ar = requests.get(asset_url, timeout=TIMEOUT)
                print(f"  {a} -> {ar.status_code}")
            except Exception as e:
                print(f"  {a} -> ERROR {e}")
        print('-'*60)
    except Exception as e:
        print(f"PAGE {page} -> ERROR {e}")
