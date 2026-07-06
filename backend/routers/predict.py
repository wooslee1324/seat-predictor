"""POST /predict — 좌석 확률 예측."""

from __future__ import annotations

from fastapi import APIRouter

from backend import services
from backend.schemas import PredictRequest, PredictResponse

router = APIRouter(tags=["예측"])


@router.post("/predict", response_model=PredictResponse, summary="좌석 확률 예측")
def predict(req: PredictRequest) -> PredictResponse:
    """출발지 → 도착지 구간의 혼잡도와 시간대별 좌석 확률을 예측한다.

    지하철은 실데이터 혼잡도를 우선 시도하고, 없으면 추정(Mock) 값으로 폴백한다.
    좌석 확률은 혼잡도에서 유도한 추정치이며 실측값이 아니다(notice 참고).
    """
    payload = services.build_prediction_payload(
        transport=req.transport,
        dep_station=req.dep_station,
        arr_station=req.arr_station,
        dep_hour=req.dep_hour,
        dep_minute=req.dep_minute,
        profile=req.profile,
    )
    return PredictResponse(**payload)
