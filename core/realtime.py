"""서울시 실시간 도착정보 연동 (프레임워크 비의존).

- 지하철 실시간 도착: swopenAPI.seoul.go.kr 의 realtimeStationArrival
- 버스 실시간 도착: ws.bus.go.kr 의 getStationByUid (정류소 ARS 번호 기준)

중요 원칙
- 이 모듈은 **실시간 '도착정보'만** 다룬다. '예상 좌석 확률'은 core.prediction 이
  담당하며, 이 값과 절대 섞지 않는다.
- 실제 좌석 수는 이 API들이 제공하지 않는다. 버스는 실시간 '혼잡도(범주값)'와
  '만차 여부'를 줄 때가 있는데, 이는 좌석 확률이 아니라 참고용 실시간 혼잡 신호다.
- 인증키가 없거나 호출이 실패하면 예외를 던지지 않고 None(제공 불가) 또는 빈
  리스트(정상 응답이나 도착 예정 없음)로 안전하게 반환한다 — 호출부는 이를 구분해
  사용자에게 알린다.

각 API의 정확한 필드명은 실제 응답으로 재확인이 필요하다("확인 필요"). 파싱은
필드가 없어도 죽지 않도록 방어적으로 작성했다.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote

import requests

# --- 지하철 실시간 도착 (서울 열린데이터광장 / TOPIS) ---
SUBWAY_REALTIME_BASE = "http://swopenapi.seoul.go.kr/api/subway"

# subwayId -> 노선명 (주요 노선). 없는 코드는 원값을 그대로 노출한다.
_SUBWAY_LINE_NAMES = {
    "1001": "1호선",
    "1002": "2호선",
    "1003": "3호선",
    "1004": "4호선",
    "1005": "5호선",
    "1006": "6호선",
    "1007": "7호선",
    "1008": "8호선",
    "1009": "9호선",
    "1063": "경의중앙선",
    "1065": "공항철도",
    "1067": "경춘선",
    "1075": "수인분당선",
    "1077": "신분당선",
    "1092": "우이신설선",
}

# --- 버스 실시간 도착 (서울 버스운행정보 공유서비스) ---
BUS_STATION_ARRIVAL_URL = "http://ws.bus.go.kr/api/rest/stationinfo/getStationByUid"

# 버스 혼잡도 코드 -> 라벨. 0(미제공)은 None 으로 처리한다.
_BUS_CONGESTION_LABELS = {
    "3": "여유",
    "4": "보통",
    "5": "혼잡",
    "6": "매우 혼잡",
}


def _to_int(value) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _subway_query_name(station_name: str) -> str:
    """realtimeStationArrival 은 '강남'처럼 '역'을 뗀 표기를 쓴다(확인 필요).

    끝의 '역'을 떼서 조회한다(예: '강남역' -> '강남'). '서울역'처럼 이름 자체에
    '역'이 포함된 일부 역은 이 방식이 안 맞을 수 있어 실제 응답으로 확인이 필요하다.
    """
    name = (station_name or "").strip()
    if name.endswith("역") and len(name) > 1:
        return name[:-1]
    return name


def _normalize_subway(row: dict) -> dict:
    return {
        "line": _SUBWAY_LINE_NAMES.get(row.get("subwayId"), row.get("subwayId")),
        "direction": row.get("updnLine"),          # 상행/하행(또는 내/외선)
        "destination": row.get("bstatnNm"),         # 종착역
        "train_line_name": row.get("trainLineNm"),  # 예: "성수행 - 건대입구방면"
        "arrival_message": row.get("arvlMsg2"),      # 예: "전역 출발", "2분 후(역이름)"
        "seconds_to_arrival": _to_int(row.get("barvlDt")),  # 도착까지 남은 초(없을 수 있음)
        "train_no": row.get("btrainNo"),
        "received_at": row.get("recptnDt"),          # 데이터 생성 시각(현재와의 차이 보정 필요)
    }


def fetch_subway_arrivals(
    auth_key: Optional[str], station_name: str, limit: int = 10, timeout: int = 8
) -> Optional[list[dict]]:
    """지하철 실시간 도착정보 목록을 반환.

    - None: 제공 불가(인증키 없음 또는 호출/파싱 실패) → 호출부에서 '미제공' 처리.
    - []  : 정상 응답이나 도착 예정 열차가 없음.
    """
    if not auth_key or not station_name:
        return None
    url = (
        f"{SUBWAY_REALTIME_BASE}/{auth_key}/json/realtimeStationArrival/"
        f"0/{limit}/{quote(_subway_query_name(station_name))}"
    )
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    rows = data.get("realtimeArrivalList")
    if not isinstance(rows, list):
        # 결과가 없거나(INFO-200 등) 오류 응답 — 정상 응답이지만 도착 정보 없음으로 처리.
        return []
    return [_normalize_subway(row) for row in rows if isinstance(row, dict)]


def _normalize_bus(item: dict) -> dict:
    congestion_code = item.get("congestion1") or item.get("congestion")
    congestion_label = None
    if congestion_code not in (None, "", "0"):
        congestion_label = _BUS_CONGESTION_LABELS.get(str(congestion_code))

    full_flag = item.get("isFullFlag1")
    is_full = None
    if full_flag not in (None, ""):
        is_full = str(full_flag) == "1"

    return {
        "route_name": item.get("rtNm"),            # 노선명
        "arrival_message": item.get("arrmsg1"),     # 예: "3분 후[2번째 전]"
        "seconds_to_arrival": _to_int(item.get("traTime1")),
        "vehicle_no": item.get("plainNo1"),          # 차량 번호판(없을 수 있음)
        "realtime_congestion": congestion_label,     # 실시간 혼잡도(제공될 때만, 좌석확률 아님)
        "is_full": is_full,                          # 만차 여부(제공될 때만)
        "stop_name": item.get("stNm"),
    }


def fetch_bus_arrivals(
    auth_key: Optional[str], ars_id: str, timeout: int = 8
) -> Optional[list[dict]]:
    """정류소(ARS 번호) 기준 버스 실시간 도착정보 목록을 반환.

    - None: 제공 불가(인증키 없음 또는 호출/파싱 실패).
    - []  : 정상 응답이나 도착 예정 버스가 없음.
    """
    if not auth_key or not ars_id:
        return None
    params = {"serviceKey": auth_key, "arsId": ars_id, "resultType": "json"}
    try:
        resp = requests.get(BUS_STATION_ARRIVAL_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    body = data.get("msgBody") if isinstance(data, dict) else None
    items = body.get("itemList") if isinstance(body, dict) else None
    if items is None:
        return []
    if isinstance(items, dict):  # 결과가 1건이면 dict 로 올 수 있음
        items = [items]
    if not isinstance(items, list):
        return []
    return [_normalize_bus(item) for item in items if isinstance(item, dict)]
