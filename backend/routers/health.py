"""GET /health — 서버 상태 확인용 헬스체크."""

from __future__ import annotations

from fastapi import APIRouter

from backend import config
from backend.schemas import HealthResponse

router = APIRouter(tags=["상태"])


@router.get("/health", response_model=HealthResponse, summary="서버 상태 확인")
def health() -> HealthResponse:
    """서버가 살아 있는지 확인한다. 배포 환경의 헬스체크에 사용."""
    return HealthResponse(status="정상", service=config.APP_TITLE, version=config.APP_VERSION)
