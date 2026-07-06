"""프레임워크에 의존하지 않는 간단한 TTL 캐시.

기존 seoul_api.py는 Streamlit의 @st.cache_data 로 무거운 API 응답을 캐싱했다.
core 패키지는 Streamlit에 의존하지 않아야 하므로, 동일한 "일정 시간 동안 결과를
재사용" 동작을 순수 파이썬으로 제공한다. 인자(위치 인자)로 캐시 키를 만들며,
인자는 문자열 등 해시 가능한 값이어야 한다.
"""

from __future__ import annotations

import functools
import time
from typing import Callable


def ttl_cache(ttl_seconds: int) -> Callable:
    """반환값을 ttl_seconds 동안 캐시하는 데코레이터.

    - 위치 인자 튜플을 캐시 키로 사용한다.
    - 만료된 항목은 다음 호출 때 자동으로 다시 계산한다.
    - wrapped.cache_clear() 로 캐시를 비울 수 있다.
    """

    def decorator(func: Callable) -> Callable:
        store: dict = {}

        @functools.wraps(func)
        def wrapper(*args):
            now = time.time()
            hit = store.get(args)
            if hit is not None:
                value, saved_at = hit
                if now - saved_at < ttl_seconds:
                    return value
            value = func(*args)
            store[args] = (value, now)
            return value

        wrapper.cache_clear = store.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
