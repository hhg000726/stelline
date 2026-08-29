import os
import requests
import json

BASE = "http://127.0.0.1:5000"
TIMEOUT = 5

def check_get(path):
    url = BASE + path
    try:
        r = requests.get(url, timeout=TIMEOUT)
        print(f"GET {path} -> {r.status_code}")
        text = r.text
        print(text[:400])
    except Exception as e:
        print(f"GET {path} -> ERROR: {e}")

def check_post(path, payload):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=TIMEOUT)
        print(f"POST {path} -> {r.status_code}")
        try:
            print(r.json())
        except Exception:
            print(r.text[:400])
    except Exception as e:
        print(f"POST {path} -> ERROR: {e}")

GET_ENDPOINTS = [
    "/api/search/force_search",
    "/api/search/not_searched",
    "/api/search/record",
    "/api/search/songs",
    "/api/bugs/rank",
    "/api/main/record",
    "/api/main/events",
    "/api/main/twits",
    "/api/congratulation/congratulations",
    "/api/offline/offline_api",
]

TEST_TOKEN = os.getenv("DEV_TEST_TOKEN", "test-token-123")

POST_ENDPOINTS = [
    ("/api/congratulation/register", {"token": TEST_TOKEN}),
    ("/api/congratulation/unregister", {"token": TEST_TOKEN}),
    ("/api/congratulation/check-token", {"token": TEST_TOKEN}),
]

if __name__ == '__main__':
    print("Starting API smoke checks against", BASE)
    for p in GET_ENDPOINTS:
        check_get(p)
        print("-"*40)
    for p, payload in POST_ENDPOINTS:
        check_post(p, payload)
        print("-"*40)
