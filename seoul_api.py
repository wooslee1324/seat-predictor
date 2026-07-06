"""하위호환 shim — 실제 구현은 core.seoul_api 로 이동했습니다.

기존 코드(app.py, mobile_demo.py)는 `import seoul_api` 후 아래 함수들을 그대로
호출합니다. 서울 공공데이터 연동 로직을 Streamlit에 의존하지 않는 core 패키지로
옮기면서, 기존 import 경로가 깨지지 않도록 이 파일에서 core.seoul_api 의 공개
함수를 그대로 다시 내보냅니다. 새 코드는 가능하면 `from core import ...` 또는
`from core.seoul_api import ...` 를 직접 사용하는 것을 권장합니다.
"""

from core.seoul_api import (
    get_bus_ridership_stat,
    get_real_congestion_series,
    get_station_options,
    get_subway_ridership_stat,
)

__all__ = [
    "get_station_options",
    "get_real_congestion_series",
    "get_bus_ridership_stat",
    "get_subway_ridership_stat",
]
