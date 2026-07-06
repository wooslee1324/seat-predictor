"""FastAPI 애플리케이션 진입점.

실행:
    uvicorn backend.main:app --reload
문서(자동 생성):
    http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import config
from backend.routers import health, predict, realtime, stations

app = FastAPI(
    title=config.APP_TITLE,
    description=config.APP_DESCRIPTION,
    version=config.APP_VERSION,
)

# 앞으로 만들 모바일 웹앱(PWA) 등 프런트에서 호출할 수 있도록 CORS 허용.
# 배포 시 ALLOWED_ORIGINS 를 실제 도메인으로 좁힌다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(stations.router)
app.include_router(predict.router)
app.include_router(realtime.router)


@app.get("/", tags=["상태"], summary="루트 안내")
def root() -> dict:
    """API 기본 안내. 사용 가능한 엔드포인트를 알려준다."""
    return {
        "service": config.APP_TITLE,
        "version": config.APP_VERSION,
        "docs": "/docs",
        "endpoints": [
            "GET /health",
            "GET /stations",
            "POST /predict",
            "GET /realtime/subway/arrivals",
            "GET /realtime/bus/arrivals",
        ],
    }
