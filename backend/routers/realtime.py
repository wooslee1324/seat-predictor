"""실시간 도착정보 엔드포인트.

- GET /realtime/subway/arrivals — 지하철 실시간 도착정보
- GET /realtime/bus/arrivals — 버스 실시간 도착정보

이 라우터는 '실시간 도착정보'만 반환한다. '예상 좌석 확률'은 POST /predict 가
담당하며, 두 정보를 한 응답에 섞지 않는다.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend import services
from backend.schemas import RealtimeBusArrivalsResponse, RealtimeSubwayArrivalsResponse

router = APIRouter(prefix="/realtime", tags=["실시간 도착정보"])


@router.get(
    "/subway/arrivals",
    response_model=RealtimeSubwayArrivalsResponse,
    summary="지하철 실시간 도착정보",
)
def subway_arrivals(
    station: str = Query(..., min_length=1, description="지하철 역명 (예: 강남역)"),
) -> RealtimeSubwayArrivalsResponse:
    """특정 역의 실시간 도착 예정 열차 정보를 반환한다.

    인증키가 없거나 호출이 실패하면 available=False 로 안전하게 응답한다(서버는
    죽지 않음). 좌석 확률은 포함하지 않는다.
    """
    return RealtimeSubwayArrivalsResponse(**services.subway_arrivals(station))


@router.get(
    "/bus/arrivals",
    response_model=RealtimeBusArrivalsResponse,
    summary="버스 실시간 도착정보",
)
def bus_arrivals(
    ars_id: str = Query(..., min_length=1, description="정류소 ARS 번호 (예: 23305)"),
) -> RealtimeBusArrivalsResponse:
    """특정 정류소(ARS 번호)의 실시간 도착 예정 버스 정보를 반환한다.

    실시간 혼잡도/만차 여부는 버스 API가 제공할 때만 담기며, 좌석 확률이 아니다.
    인증키 없음/호출 실패 시 available=False 로 안전하게 응답한다.
    """
    return RealtimeBusArrivalsResponse(**services.bus_arrivals(ars_id))
