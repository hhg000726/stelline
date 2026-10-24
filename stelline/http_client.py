"""외부 HTTP 호출에 쓰는 공용 세션.

`requests.get()`/`requests.post()`는 호출마다 새 Session을 만들어 커넥션 풀과
TLS 핸드셰이크를 버린다. 백그라운드 작업은 같은 호스트(YouTube/FCM)를 수십~수백
번 연달아 부르므로, 세션 하나를 재사용해 연결을 살려 두는 편이 훨씬 싸다.

재시도는 일부러 켜지 않는다. 지금 호출부는 `RequestException`을 잡아 쿼터 초과나
크롤링 실패를 판정하는데, 자동 재시도가 끼면 그 판정 시점과 횟수가 달라진다.
"""

import re
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter

# 한 호스트에 동시에 물리는 연결 수. 작업들이 순차 호출이라 크게 잡을 이유가 없다.
_POOL_SIZE = 10

# 응답이 없을 때는 예외 이름이 곧 원인이다. 자주 보는 것만 한국어로 바꾼다.
_ERROR_NAMES = {
    "ReadTimeout": "응답 시간 초과",
    "ConnectTimeout": "연결 시간 초과",
    "Timeout": "시간 초과",
    "ConnectionError": "연결 실패",
    "SSLError": "TLS 오류",
}
_TAG_RE = re.compile(r"<[^>]+>")


def _build_session():
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=_POOL_SIZE, pool_maxsize=_POOL_SIZE, max_retries=0)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = _build_session()


def describe_request_error(error):
    """requests 예외를 요청 주소 없이 한 줄로 줄인다. 로그에는 이것을 남긴다.

    `HTTPError` 의 기본 문구에는 요청 주소가 통째로 들어가, 주소에 키를 싣는 YouTube API 는
    실패할 때마다 키가 로그에 그대로 남았다. 주소 대신 상태 코드와 Google 이 알려 주는
    사유(quotaExceeded·rateLimitExceeded·keyInvalid 등)를 남긴다. 무엇에 막혔는지는 주소보다
    이쪽이 훨씬 잘 말해 준다. 예) `HTTP 403 quotaExceeded (www.googleapis.com): The request …`
    """
    response = getattr(error, "response", None)
    request = getattr(error, "request", None) or getattr(response, "request", None)
    url = getattr(request, "url", None) or getattr(response, "url", None)
    host = urlsplit(url).hostname if isinstance(url, str) else None
    where = f" ({host})" if host else ""
    if response is None:
        name = type(error).__name__
        return f"{_ERROR_NAMES.get(name, name)}{where}"

    reason, message = _google_error_reason(response)
    summary = f"HTTP {response.status_code}{' ' + reason if reason else ''}{where}"
    return f"{summary}: {message}" if message else summary


def _google_error_reason(response):
    """Google API 오류 본문에서 사유와 설명을 꺼낸다. 다른 모양이면 빈 값을 돌려준다."""
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return "", ""
    if not isinstance(error, dict):
        return "", ""
    details = error.get("errors")
    first = details[0] if isinstance(details, list) and details and isinstance(details[0], dict) else {}
    reason = first.get("reason") or error.get("status") or ""
    # 설명에 링크용 태그가 섞여 온다(…your <a href="…">quota</a>.). 글자만 남기고 줄인다.
    message = " ".join(_TAG_RE.sub("", str(error.get("message") or "")).split())
    return str(reason), message[:200]
