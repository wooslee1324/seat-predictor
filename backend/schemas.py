"""API 요청/응답 스키마(Pydantic 모델).

응답 문구는 모두 한국어를 기준으로 한다.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

TransportType = Literal["지하철", "버스"]
ProfileType = Literal["web", "mobile"]


class HealthResponse(BaseModel):
    status: str = Field("정상", description="서버 상태")
    service: str = Field(..., description="서비스 이름")
    version: str = Field(..., description="API 버전")


class StationsResponse(BaseModel):
    stations: list[str] = Field(..., description="선택 가능한 지하철 역 목록")
    count: int = Field(..., description="역 개수")
    source: str = Field(..., description="목록 출처 — '실데이터' 또는 '기본목록'")


class PredictRequest(BaseModel):
    transport: TransportType = Field(..., description="교통수단 (지하철 또는 버스)")
    dep_station: str = Field(..., min_length=1, description="출발역/정류장")
    arr_station: str = Field(..., min_length=1, description="도착역/정류장")
    dep_hour: int = Field(..., ge=0, le=23, description="퇴근(출발) 시각의 시 (0~23)")
    dep_minute: int = Field(0, ge=0, le=59, description="퇴근(출발) 시각의 분 (0~59)")
    profile: ProfileType = Field("web", description="예측 프리셋 — web 또는 mobile")

    model_config = {
        "json_schema_extra": {
            "example": {
                "transport": "지하철",
                "dep_station": "강남역",
                "arr_station": "사당역",
                "dep_hour": 18,
                "dep_minute": 30,
                "profile": "web",
            }
        }
    }


class SeriesPoint(BaseModel):
    minutes_offset: int = Field(..., description="기준 시각으로부터의 경과 분")
    time_label: str = Field(..., description="해당 시각 라벨 (HH:MM)")
    congestion_pct: float = Field(..., description="혼잡도 (%)")
    seat_prob_pct: float = Field(..., description="앉아서 갈 확률 (%)")


class RouteInfo(BaseModel):
    transport: TransportType
    dep_station: str
    arr_station: str
    dep_time: str = Field(..., description="출발 시각 (HH:MM)")


class CurrentInfo(BaseModel):
    congestion_pct: float = Field(..., description="현재 혼잡도 (%)")
    seat_prob_pct: float = Field(..., description="현재 앉아서 갈 확률 (%)")
    level_label: str = Field(..., description="혼잡도 등급 라벨")
    level_emoji: str = Field(..., description="혼잡도 등급 이모지")


class Recommendation(BaseModel):
    best_offset_min: int = Field(..., description="추천 탑승까지의 대기 분")
    best_time_label: str = Field(..., description="추천 탑승 시각 (HH:MM)")
    best_seat_prob_pct: float = Field(..., description="추천 탑승 시 앉아서 갈 확률 (%)")
    wait_spot: str = Field(..., description="추천 대기 위치")
    message: str = Field(..., description="사용자 안내 문구")


class PredictResponse(BaseModel):
    route: RouteInfo
    is_real: bool = Field(..., description="혼잡도가 실데이터에서 왔는지 여부")
    data_line: Optional[str] = Field(None, description="실데이터일 때의 노선명")
    data_source: str = Field(..., description="'실데이터' 또는 '추정(Mock)'")
    current: CurrentInfo
    recommendation: Recommendation
    series: list[SeriesPoint]
    notice: str = Field(..., description="좌석 확률이 추정치임을 알리는 안내 문구")
