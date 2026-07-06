"""서비스 계층 — core 로직을 호출해 API 응답 형태로 가공한다.

라우터는 이 모듈만 호출하고, core 의 세부 구현에는 직접 의존하지 않는다.
core 로직 자체는 건드리지 않으므로 데모(app.py, mobile_demo.py)와 결과가 같다.
"""

from __future__ import annotations

from core import realtime, seoul_api
from core.prediction import MOBILE_PRESET, WEB_PRESET, build_prediction, congestion_level

from backend import config

# 실시간 도착정보 응답에 항상 붙이는 안내 — 좌석 확률과의 구분을 명확히 한다.
REALTIME_NOTICE = (
    "이 응답은 실시간 '도착정보'만 담고 있습니다. 예상 좌석 확률은 포함되지 않으며, "
    "좌석 확률은 POST /predict 에서 별도(추정치)로 제공합니다."
)

# 예측 곡선의 시간 오프셋(0,5,...,60분) — core.build_prediction 과 동일 기준.
MINUTES_OFFSETS = list(range(0, 65, 5))

_PRESETS = {"web": WEB_PRESET, "mobile": MOBILE_PRESET}

_SEAT_GAIN_THRESHOLD = 5.0  # 이 이상 좋아지면 "조금 기다렸다 타라"고 안내


def list_stations() -> tuple[list[str], str]:
    """(역 목록, 출처) 반환. 실데이터를 못 받으면 기본 목록으로 폴백한다."""
    key = config.congestion_key()
    options = seoul_api.get_station_options(key)
    if options:
        return options, "실데이터"
    return list(config.FALLBACK_STATIONS), "기본목록"


def build_prediction_payload(
    transport: str,
    dep_station: str,
    arr_station: str,
    dep_hour: int,
    dep_minute: int,
    profile: str = "web",
) -> dict:
    """예측을 수행하고 API 응답용 dict 를 만든다."""
    preset = _PRESETS.get(profile, WEB_PRESET)
    key = config.congestion_key()

    # 지하철만 실데이터 혼잡도를 시도한다(없으면 mock 으로 폴백).
    real = None
    if transport == "지하철":
        real = seoul_api.get_real_congestion_series(
            key, dep_station, dep_hour, dep_minute, MINUTES_OFFSETS
        )
    real_pct = tuple(real["congestion_pct"]) if real else None
    real_line = real["line"] if real else None

    df, wait_spot, is_real, data_line = build_prediction(
        preset, transport, dep_station, arr_station, dep_hour, dep_minute, real_pct, real_line
    )

    current_congestion = float(df.iloc[0]["congestion_pct"])
    current_seat_prob = float(df.iloc[0]["seat_prob_pct"])
    level_label, level_emoji = congestion_level(current_congestion)

    # 0~30분 사이에서 앉아서 갈 확률이 가장 높은 시점을 추천한다.
    future = df[(df["minutes_offset"] > 0) & (df["minutes_offset"] <= 30)]
    best_row = future.loc[future["seat_prob_pct"].idxmax()]
    best_offset = int(best_row["minutes_offset"])
    best_prob = float(best_row["seat_prob_pct"])
    best_time_label = str(best_row["time_label"])

    if best_prob - current_seat_prob >= _SEAT_GAIN_THRESHOLD:
        message = (
            f"{best_offset}분 뒤({best_time_label})에 타면 앉아서 갈 확률이 "
            f"{best_prob:.0f}%로 올라갑니다. {wait_spot}에서 대기하세요."
        )
    else:
        message = (
            f"지금 타는 것이 가장 좋습니다. 현재 앉아서 갈 확률은 "
            f"{current_seat_prob:.0f}%입니다. {wait_spot}에서 대기하세요."
        )

    series = [
        {
            "minutes_offset": int(row.minutes_offset),
            "time_label": str(row.time_label),
            "congestion_pct": float(row.congestion_pct),
            "seat_prob_pct": float(row.seat_prob_pct),
        }
        for row in df.itertuples(index=False)
    ]

    return {
        "route": {
            "transport": transport,
            "dep_station": dep_station,
            "arr_station": arr_station,
            "dep_time": f"{dep_hour:02d}:{dep_minute:02d}",
        },
        "is_real": bool(is_real),
        "data_line": data_line,
        "data_source": "실데이터" if is_real else "추정(Mock)",
        "current": {
            "congestion_pct": current_congestion,
            "seat_prob_pct": current_seat_prob,
            "level_label": level_label,
            "level_emoji": level_emoji,
        },
        "recommendation": {
            "best_offset_min": best_offset,
            "best_time_label": best_time_label,
            "best_seat_prob_pct": best_prob,
            "wait_spot": wait_spot,
            "message": message,
        },
        "series": series,
        "notice": (
            "앉아서 갈 확률은 혼잡도로부터 유도한 추정치이며 실측값이 아닙니다. "
            "혼잡도는 실데이터를 찾은 경우 서울시 공공데이터를, 찾지 못한 경우 "
            "추정(Mock) 값을 사용합니다."
        ),
    }


def subway_arrivals(station: str) -> dict:
    """지하철 실시간 도착정보를 조회해 응답 dict 를 만든다(예상 좌석 확률 미포함).

    인증키가 없거나 호출이 실패해도 예외를 던지지 않고 available=False 로 안내한다.
    """
    key = config.subway_realtime_key()
    arrivals = realtime.fetch_subway_arrivals(key, station)

    if arrivals is None:
        reason = "인증키가 설정되지 않았습니다." if not key else "실시간 API 호출에 실패했습니다."
        return {
            "station": station,
            "available": False,
            "data_source": "미제공",
            "arrivals": [],
            "message": f"실시간 지하철 도착정보를 제공할 수 없습니다 — {reason}",
            "notice": REALTIME_NOTICE,
        }

    message = (
        "실시간 도착정보를 불러왔습니다."
        if arrivals
        else "현재 도착 예정 열차 정보가 없습니다."
    )
    return {
        "station": station,
        "available": True,
        "data_source": "실시간 도착정보",
        "arrivals": arrivals,
        "message": message,
        "notice": REALTIME_NOTICE,
    }


def bus_arrivals(ars_id: str) -> dict:
    """정류소(ARS 번호) 기준 버스 실시간 도착정보를 조회해 응답 dict 를 만든다.

    실시간 혼잡도/만차 여부는 버스 API가 줄 때만 담기며, 이는 '예상 좌석 확률'이
    아니라 참고용 실시간 혼잡 신호다. 인증키 없음/호출 실패 시 available=False.
    """
    key = config.bus_realtime_key()
    arrivals = realtime.fetch_bus_arrivals(key, ars_id)

    if arrivals is None:
        reason = "인증키가 설정되지 않았습니다." if not key else "실시간 API 호출에 실패했습니다."
        return {
            "ars_id": ars_id,
            "available": False,
            "data_source": "미제공",
            "arrivals": [],
            "message": f"실시간 버스 도착정보를 제공할 수 없습니다 — {reason}",
            "notice": REALTIME_NOTICE,
        }

    message = (
        "실시간 도착정보를 불러왔습니다."
        if arrivals
        else "현재 도착 예정 버스 정보가 없습니다."
    )
    return {
        "ars_id": ars_id,
        "available": True,
        "data_source": "실시간 도착정보",
        "arrivals": arrivals,
        "message": message,
        "notice": REALTIME_NOTICE,
    }
