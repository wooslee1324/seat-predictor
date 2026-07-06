"""GET /stations — 선택 가능한 지하철 역 목록."""

from __future__ import annotations

from fastapi import APIRouter

from backend import services
from backend.schemas import StationsResponse

router = APIRouter(tags=["역 정보"])


@router.get("/stations", response_model=StationsResponse, summary="지하철 역 목록 조회")
def stations() -> StationsResponse:
    """지하철 역 목록을 반환한다.

    인증키가 있으면 서울시 공공데이터 기반 실제 역 목록을, 없으면 기본 역 목록을
    돌려준다(출처는 source 필드로 구분).
    """
    names, source = services.list_stations()
    return StationsResponse(stations=names, count=len(names), source=source)
