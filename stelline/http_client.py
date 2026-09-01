"""외부 HTTP 호출에 쓰는 공용 세션.

`requests.get()`/`requests.post()`는 호출마다 새 Session을 만들어 커넥션 풀과
TLS 핸드셰이크를 버린다. 백그라운드 작업은 같은 호스트(YouTube/FCM)를 수십~수백
번 연달아 부르므로, 세션 하나를 재사용해 연결을 살려 두는 편이 훨씬 싸다.

재시도는 일부러 켜지 않는다. 지금 호출부는 `RequestException`을 잡아 쿼터 초과나
크롤링 실패를 판정하는데, 자동 재시도가 끼면 그 판정 시점과 횟수가 달라진다.
"""

import requests
from requests.adapters import HTTPAdapter

# 한 호스트에 동시에 물리는 연결 수. 작업들이 순차 호출이라 크게 잡을 이유가 없다.
_POOL_SIZE = 10


def _build_session():
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=_POOL_SIZE, pool_maxsize=_POOL_SIZE, max_retries=0)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = _build_session()
