"""서울 열린데이터광장 실데이터 연동. 지금은 지하철 혼잡도(subwConfusion)만 지원한다.

subwConfusion API는 역/노선으로 필터링하는 요청 파라미터가 없어서, 전체 데이터
(약 1,671건)를 한 번에 받아 캐싱한 뒤 파이썬에서 역명으로 걸러낸다. 데이터
갱신주기가 분기별이라 캐시 TTL을 길게(30일) 잡는다.
"""

from typing import Optional

import numpy as np
import pandas as pd
import requests
import streamlit as st
import xml.etree.ElementTree as ET

CONGESTION_SERVICE = "subwConfusion"
CONGESTION_BASE_URL = "http://openapi.seoul.go.kr:8088"
CONGESTION_PAGE_SIZE = 1000
CONGESTION_CACHE_TTL = 60 * 60 * 24 * 30  # 30일 — 데이터가 분기별로만 갱신됨


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
        url = f"{CONGESTION_BASE_URL}/{auth_key}/xml/{CONGESTION_SERVICE}/{start}/{end}/"
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
