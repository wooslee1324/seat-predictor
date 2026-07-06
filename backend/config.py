"""백엔드 설정 — 서울 공공데이터 인증키 로드 등.

인증키는 아래 우선순위로 읽는다.
1) 환경변수 (배포 환경 권장): SEOUL_SUBWAY_CONGESTION_KEY 등
2) .streamlit/secrets.toml 의 [seoul_api] 섹션 (로컬 개발 편의 — 데모와 키 공유)

인증키 파일(.streamlit/secrets.toml)은 절대 커밋하지 않는다(.gitignore 로 제외).
키가 하나도 없어도 서버는 정상 동작하며, 이 경우 실데이터 대신 기본 역 목록과
추정(Mock) 예측으로 응답한다.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    import tomllib  # Python 3.11+ 표준 라이브러리
except ModuleNotFoundError:  # pragma: no cover - 구버전 파이썬 방어
    tomllib = None  # type: ignore[assignment]

# backend/ 의 부모가 프로젝트 루트
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SECRETS_PATH = _PROJECT_ROOT / ".streamlit" / "secrets.toml"

# core.seoul_api / 데모가 쓰는 키 이름 -> 환경변수 이름 매핑
_ENV_MAP = {
    "subway_congestion_key": "SEOUL_SUBWAY_CONGESTION_KEY",
    "subway_ridership_key": "SEOUL_SUBWAY_RIDERSHIP_KEY",
    "bus_ridership_key": "SEOUL_BUS_RIDERSHIP_KEY",
}

APP_TITLE = "오늘 좌석 예측기 API"
APP_DESCRIPTION = "서울시 공공데이터 기반 퇴근길 좌석 확률 예측 API"
APP_VERSION = "0.1.0"

# 개발 단계에서는 모든 오리진 허용 — 실제 배포 시 PWA 도메인으로 좁힐 것.
ALLOWED_ORIGINS = ["*"]

# 실데이터 역 목록을 못 받아올 때 쓰는 기본 역 목록(데모와 동일).
FALLBACK_STATIONS = [
    "강남역",
    "사당역",
    "잠실역",
    "홍대입구역",
    "서울역",
    "신도림역",
    "건대입구역",
    "시청역",
    "교대역",
    "을지로입구역",
]


@lru_cache
def _secrets_file_keys() -> dict:
    """.streamlit/secrets.toml 의 [seoul_api] 섹션을 읽어 dict 로 반환(없으면 빈 dict)."""
    if tomllib is None or not _SECRETS_PATH.exists():
        return {}
    try:
        with _SECRETS_PATH.open("rb") as fp:
            data = tomllib.load(fp)
    except Exception:
        return {}
    section = data.get("seoul_api", {})
    return dict(section) if isinstance(section, dict) else {}


def get_auth_key(name: str) -> Optional[str]:
    """인증키 조회 — 환경변수 우선, 없으면 secrets.toml 에서 찾는다."""
    env_name = _ENV_MAP.get(name)
    if env_name:
        value = os.getenv(env_name)
        if value:
            return value
    return _secrets_file_keys().get(name)


def congestion_key() -> Optional[str]:
    """지하철 혼잡도 실데이터용 인증키(없으면 None)."""
    return get_auth_key("subway_congestion_key")
