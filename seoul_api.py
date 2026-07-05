"""서울 열린데이터광장 실데이터 연동.

- 지하철 혼잡도(subwConfusion): 예측용 실데이터. 시간대별 값을 제공해 좌석 확률
  곡선 계산에 직접 쓰인다.
- 지하철 역 승하차 인원(CardSubwayStatsNew) / 버스 정류장 승하차 인원
  (CardBusStatisticsServiceNew): 둘 다 참고 지표 전용. 역·정류장/노선당
  "하루 총합"만 주고 시간대 구분이 없어서 예측(혼잡도·좌석 확률) 계산에는 쓸 수
  없다 — "오늘 이 역/정류장 하루 이용객 약 N명" 같은 트리비아로만 노출한다.
"""

from datetime import date, timedelta
from typing import Optional
import re

import numpy as np
import pandas as pd
import requests
import streamlit as st
import xml.etree.ElementTree as ET

SEOUL_OPENAPI_BASE_URL = "http://openapi.seoul.go.kr:8088"

CONGESTION_SERVICE = "subwConfusion"
CONGESTION_PAGE_SIZE = 1000
CONGESTION_CACHE_TTL = 60 * 60 * 24 * 30  # 30일 — 데이터가 분기별로만 갱신됨

BUS_RIDERSHIP_SERVICE = "CardBusStatisticsServiceNew"
BUS_RIDERSHIP_PAGE_SIZE = 1000
BUS_RIDERSHIP_MAX_PAGES = 60  # 안전판 — 하루 전체가 약 41,500건(=42페이지)
BUS_RIDERSHIP_CACHE_TTL = 60 * 60 * 24  # 하루 — use_date가 매일 바뀌므로 자연 갱신
BUS_RIDERSHIP_DATA_LAG_DAYS = 3  # "매일 3일전 데이터를 갱신" — README/데이터셋 설명 기준
BUS_RIDERSHIP_MAX_MATCHED_STOPS = 15  # 이보다 많이 매칭되면 너무 모호하다고 보고 표시 안 함

SUBWAY_RIDERSHIP_SERVICE = "CardSubwayStatsNew"
SUBWAY_RIDERSHIP_PAGE_SIZE = 1000
SUBWAY_RIDERSHIP_MAX_PAGES = 5  # 안전판 — 하루 전체가 약 618건(1페이지면 충분)
SUBWAY_RIDERSHIP_CACHE_TTL = 60 * 60 * 24  # 하루
SUBWAY_RIDERSHIP_DATA_LAG_DAYS = 3


def _time_columns():
    """TIME0530..TIME2330(당일) + TIME0000/TIME0030(익일)을 분단위 오프셋과 함께 반환."""
    cols = [(minute, f"TIME{minute // 60:02d}{minute % 60:02d}") for minute in range(330, 1440, 30)]
    cols += [(1440, "TIME0000"), (1470, "TIME0030")]
    return cols


_TIME_COLUMNS = _time_columns()


def _fetch_all_rows(auth_key: str) -> list:
    rows = []
    start = 1
    while True:
        end = start + CONGESTION_PAGE_SIZE - 1
        url = f"{SEOUL_OPENAPI_BASE_URL}/{auth_key}/xml/{CONGESTION_SERVICE}/{start}/{end}/"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        code = root.findtext("RESULT/CODE")
        if code and code != "INFO-000":
            raise RuntimeError(f"Seoul API error {code}: {root.findtext('RESULT/MESSAGE')}")

        total = int(root.findtext("list_total_count", "0"))
        row_elements = root.findall("row")
        rows.extend({child.tag: child.text for child in row_el} for row_el in row_elements)

        if not row_elements or start + len(row_elements) - 1 >= total:
            break
        start += CONGESTION_PAGE_SIZE
    return rows


@st.cache_data(ttl=CONGESTION_CACHE_TTL, show_spinner=False)
def _load_congestion_table(auth_key: str) -> pd.DataFrame:
    records = [
        {
            "station": row.get("DPTRE_STTN"),
            "line": row.get("LINE"),
            "dow": row.get("DOW_SE"),
            "direction": row.get("UP_DOWN_SE"),
            "minute_of_day": minute,
            "congestion_pct": float(row[col]),
        }
        for row in _fetch_all_rows(auth_key)
        for minute, col in _TIME_COLUMNS
        if row.get(col) is not None
    ]
    return pd.DataFrame.from_records(records)


def _station_name_variants(name: str) -> list:
    """subwConfusion은 '강남'처럼 역 이름에서 '역'을 뗀 표기를 쓰지만 '서울역'처럼
    '역'이 이름 자체에 포함된 경우도 있어 양쪽 다 시도한다."""
    name = name.strip()
    if name.endswith("역") and len(name) > 1:
        return [name, name[:-1]]
    return [name, name + "역"]


def _display_name(raw_name: str) -> str:
    """UI에 보여줄 표준 표기 — '강남' -> '강남역', '서울역' -> '서울역' 그대로."""
    return raw_name if raw_name.endswith("역") else f"{raw_name}역"


def get_station_options(auth_key: Optional[str]) -> list:
    """selectbox에 채울 실제 지하철 역명 목록. 조회 실패 시 빈 리스트를 반환하므로
    호출부에서 비어 있으면 자유 텍스트 입력으로 폴백해야 한다."""
    if not auth_key:
        return []
    try:
        table = _load_congestion_table(auth_key)
    except Exception:
        return []
    names = {_display_name(n) for n in table["station"].dropna().unique()}
    return sorted(names)


def get_real_congestion_series(
    auth_key: Optional[str],
    station_name: str,
    dep_hour: int,
    dep_minute: int,
    minutes_offsets,
    dow: str = "평일",
) -> Optional[dict]:
    """실제 혼잡도 데이터로 minutes_offsets에 대응하는 값을 보간해 반환.

    매핑 실패, API 오류, 요청 시간이 데이터 범위(05:30~다음날 00:30) 밖이면
    None을 반환한다 — 호출부에서 mock으로 폴백해야 한다.
    """
    if not auth_key:
        return None
    try:
        table = _load_congestion_table(auth_key)
    except Exception:
        return None

    variants = _station_name_variants(station_name)
    matched = table[table["station"].isin(variants) & (table["dow"] == dow)]
    if matched.empty:
        return None

    # 역이 여러 노선에 걸쳐 있으면(예: 사당 2/4호선) 결정적으로 첫 노선만 사용.
    # 상/하선(또는 내/외선)은 구분 입력을 받지 않으므로 평균낸다.
    line_used = sorted(matched["line"].unique())[0]
    matched = matched[matched["line"] == line_used]
    curve = matched.groupby("minute_of_day")["congestion_pct"].mean().sort_index()

    x = curve.index.to_numpy(dtype=float)
    y = curve.to_numpy(dtype=float)
    base_minute = dep_hour * 60 + dep_minute
    requested = base_minute + np.asarray(minutes_offsets, dtype=float)

    if requested.min() < x.min() or requested.max() > x.max():
        return None

    return {
        "congestion_pct": np.interp(requested, x, y),
        "line": line_used,
        "dow": dow,
    }


def _fetch_bus_rows(auth_key: str, use_date: str) -> list:
    rows = []
    start = 1
    for _ in range(BUS_RIDERSHIP_MAX_PAGES):
        end = start + BUS_RIDERSHIP_PAGE_SIZE - 1
        url = f"{SEOUL_OPENAPI_BASE_URL}/{auth_key}/xml/{BUS_RIDERSHIP_SERVICE}/{start}/{end}/{use_date}/"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        code = root.findtext("RESULT/CODE")
        if code and code != "INFO-000":
            raise RuntimeError(f"Seoul API error {code}: {root.findtext('RESULT/MESSAGE')}")

        total = int(root.findtext("list_total_count", "0"))
        row_elements = root.findall("row")
        rows.extend({child.tag: child.text for child in row_el} for row_el in row_elements)

        if not row_elements or start + len(row_elements) - 1 >= total:
            break
        start += BUS_RIDERSHIP_PAGE_SIZE
    return rows


@st.cache_data(ttl=BUS_RIDERSHIP_CACHE_TTL, show_spinner=False)
def _load_bus_ridership_table(auth_key: str, use_date: str) -> pd.DataFrame:
    records = [
        {
            "stop_name": row.get("SBWY_STNS_NM"),
            "route_name": row.get("RTE_NM"),
            "boarding": float(row["GTON_TNOPE"]) if row.get("GTON_TNOPE") else 0.0,
            "alighting": float(row["GTOFF_TNOPE"]) if row.get("GTOFF_TNOPE") else 0.0,
        }
        for row in _fetch_bus_rows(auth_key, use_date)
    ]
    return pd.DataFrame.from_records(records)


def _clean_bus_stop_name(name: str) -> str:
    """정류장명 끝의 ARS 번호 괄호를 뗀다 — '강남역10번출구(00041)' -> '강남역10번출구'."""
    return re.sub(r"\([^)]*\)$", "", name or "").strip()


def get_bus_ridership_stat(auth_key: Optional[str], stop_name: str, use_date: Optional[str] = None) -> Optional[dict]:
    """정류장 하루 총 승하차 인원(참고 지표). 좌석 확률/혼잡도 계산에는 쓰이지 않는다.

    CardBusStatisticsServiceNew는 정류장명 필터 파라미터가 없어 하루 전체(약
    41,500건)를 받아서 우리 쪽에서 걸러야 하고, 이름 표기도 'OO역10번출구(ARS번호)'
    형태라 사용자가 입력한 문자열과 정확히 일치하지 않는 경우가 많다. 입력을
    '.'/공백 기준으로 토큰화해 부분일치하는 정류장을 모두 찾고, 매칭된 정류장
    수가 너무 많으면(15개 초과) 너무 모호하다고 보고 None을 반환한다.
    """
    if not auth_key:
        return None
    if use_date is None:
        use_date = (date.today() - timedelta(days=BUS_RIDERSHIP_DATA_LAG_DAYS)).strftime("%Y%m%d")

    try:
        table = _load_bus_ridership_table(auth_key, use_date)
    except Exception:
        return None
    if table.empty:
        return None

    tokens = [t for t in re.split(r"[.\s]", stop_name.strip()) if len(t) >= 2]
    if not tokens:
        return None

    clean_names = table["stop_name"].map(_clean_bus_stop_name)
    mask = clean_names.apply(lambda c: any(t in c for t in tokens))
    matched = table[mask]
    if matched.empty:
        return None

    stop_count = matched["stop_name"].nunique()
    if stop_count > BUS_RIDERSHIP_MAX_MATCHED_STOPS:
        return None  # 너무 광범위하게 매칭됨 — 신뢰할 수 없는 집계라 표시하지 않음

    return {
        "boarding": int(matched["boarding"].sum()),
        "alighting": int(matched["alighting"].sum()),
        "stop_count": stop_count,
        "route_count": matched["route_name"].nunique(),
        "date": use_date,
    }


def _fetch_subway_ridership_rows(auth_key: str, use_date: str) -> list:
    rows = []
    start = 1
    for _ in range(SUBWAY_RIDERSHIP_MAX_PAGES):
        end = start + SUBWAY_RIDERSHIP_PAGE_SIZE - 1
        url = f"{SEOUL_OPENAPI_BASE_URL}/{auth_key}/xml/{SUBWAY_RIDERSHIP_SERVICE}/{start}/{end}/{use_date}/"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        code = root.findtext("RESULT/CODE")
        if code and code != "INFO-000":
            raise RuntimeError(f"Seoul API error {code}: {root.findtext('RESULT/MESSAGE')}")

        total = int(root.findtext("list_total_count", "0"))
        row_elements = root.findall("row")
        rows.extend({child.tag: child.text for child in row_el} for row_el in row_elements)

        if not row_elements or start + len(row_elements) - 1 >= total:
            break
        start += SUBWAY_RIDERSHIP_PAGE_SIZE
    return rows


@st.cache_data(ttl=SUBWAY_RIDERSHIP_CACHE_TTL, show_spinner=False)
def _load_subway_ridership_table(auth_key: str, use_date: str) -> pd.DataFrame:
    records = [
        {
            "station": row.get("SBWY_STNS_NM"),
            "line": row.get("SBWY_ROUT_LN_NM"),
            "boarding": float(row["GTON_TNOPE"]) if row.get("GTON_TNOPE") else 0.0,
            "alighting": float(row["GTOFF_TNOPE"]) if row.get("GTOFF_TNOPE") else 0.0,
        }
        for row in _fetch_subway_ridership_rows(auth_key, use_date)
    ]
    return pd.DataFrame.from_records(records)


def get_subway_ridership_stat(
    auth_key: Optional[str], station_name: str, use_date: Optional[str] = None
) -> Optional[dict]:
    """역 하루 총 승하차 인원(참고 지표). 좌석 확률/혼잡도 계산에는 쓰이지 않는다.

    CardSubwayStatsNew도 역/노선당 하루 총합만 주고 시간대 구분이 없다. 다만
    역명 표기가 subwConfusion과 같은 관례(강남역 -> "강남")라 기존
    _station_name_variants를 그대로 재사용해 정확히 매칭한다. 여러 노선에
    걸친 역(예: 사당 2/4호선)은 전 노선 합산.
    """
    if not auth_key:
        return None
    if use_date is None:
        use_date = (date.today() - timedelta(days=SUBWAY_RIDERSHIP_DATA_LAG_DAYS)).strftime("%Y%m%d")

    try:
        table = _load_subway_ridership_table(auth_key, use_date)
    except Exception:
        return None
    if table.empty:
        return None

    variants = _station_name_variants(station_name)
    matched = table[table["station"].isin(variants)]
    if matched.empty:
        return None

    return {
        "boarding": int(matched["boarding"].sum()),
        "alighting": int(matched["alighting"].sum()),
        "line_count": matched["line"].nunique(),
        "date": use_date,
    }
