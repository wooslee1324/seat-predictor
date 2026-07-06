"""seat-predictor 도메인 로직 패키지.

이 패키지는 Streamlit·FastAPI 등 특정 프레임워크에 의존하지 않는 순수 파이썬
모듈만 담는다. 발표용 데모(app.py, mobile_demo.py)와 앞으로 만들 백엔드 API가
동일한 예측·데이터 로직을 공유하도록 하는 것이 목적이다.
"""

from core.prediction import (
    MOBILE_PRESET,
    WEB_PRESET,
    PredictionConfig,
    build_prediction,
    congestion_level,
    congestion_level_color,
)

__all__ = [
    "PredictionConfig",
    "WEB_PRESET",
    "MOBILE_PRESET",
    "build_prediction",
    "congestion_level",
    "congestion_level_color",
]
