"""Streamlit mobile-style demo for the seat predictor."""

from datetime import time
from html import escape
from typing import Optional

import plotly.graph_objects as go
import streamlit as st

import seoul_api
from core.prediction import MOBILE_PRESET, build_prediction, congestion_level_color


st.set_page_config(
    page_title="오늘 좌석 모바일 데모",
    page_icon="🚇",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        /* warm beige/brown mood: cream page, ivory cards, caramel-brown action color */
        --bg: #f6efe7;
        --surface: #fffaf4;
        --surface-strong: #f0e2d2;
        --surface-soft: #fbf5ee;

        --text: #3b2a1f;
        --text-soft: #6f5a48;
        --muted: #9a8775;

        --primary: #8b5e3c;
        --primary-dark: #5f3d28;
        --primary-soft: #ead7c3;

        --accent: #7a8f63;
        --accent-soft: #e8edde;

        --warning: #c98a3a;
        --danger: #b85c38;

        --border: #e1d2c1;
        --shadow: 0 12px 32px rgba(87, 62, 42, 0.12);

        /* unified radius tokens + a CTA-specific glow, carried over from the previous pass */
        --radius-sm: 10px;
        --radius: 14px;
        --radius-lg: 18px;
        --shadow-cta: 0 14px 28px rgba(139, 94, 60, 0.32);

        /* 기존 core.congestion_level_color 가 쓰는 색 토큰을 베이지 팔레트에 매핑 */
        --red: var(--danger);
        --amber: var(--warning);
        --teal: var(--primary);
        --green: var(--accent);
    }

    .stApp {
        background: var(--bg);
        color: var(--text);
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    .block-container {
        max-width: 430px;
        padding: 18px 16px 92px;
    }

    /* Hero: logo lockup + tagline live in one visually separated card so the
       page reads as "brand block, then tool" instead of a single dense strip. */
    .hero {
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        padding: 22px 20px 24px;
        margin-bottom: 22px;
        /* faint beige-brown wash instead of a flat card, so the hero still feels "designed" */
        background:
            radial-gradient(120% 140% at 0% 0%, var(--primary-soft), transparent 55%),
            var(--surface);
        box-shadow: var(--shadow);
    }

    .brand-lockup {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .brand-icon {
        font-size: 1.9rem;
        line-height: 1;
    }

    .brand-text {
        display: flex;
        flex-direction: column;
        min-width: 0;
    }

    .brand-name {
        font-size: 1.5rem;
        line-height: 1.2;
        font-weight: 850;
        color: var(--text);
        letter-spacing: -0.01em;
    }

    .brand-tagline {
        margin-top: 2px;
        color: var(--text-soft);
        font-size: 0.8rem;
    }

    .hero-desc {
        margin: 16px 0 0;
        color: var(--text-soft);
        font-size: 0.92rem;
        line-height: 1.55;
    }

    .status-pill {
        border: 1px solid var(--border);
        border-radius: 999px;
        color: var(--muted);
        padding: 6px 10px;
        font-size: 0.76rem;
        white-space: nowrap;
        background: rgba(59, 42, 31, 0.04);
    }

    .section-title {
        margin: 18px 0 8px;
        font-size: 0.86rem;
        color: var(--muted);
        font-weight: 720;
    }

    /* the transport toggle sits directly under the hero, so it doesn't need
       the hero's own bottom margin stacked on top of section-title's usual gap */
    .hero + .section-title {
        margin-top: 0;
    }

    .route-strip {
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 13px 14px;
        margin-bottom: 14px;
        background: var(--surface);
        box-shadow: var(--shadow);
    }

    .route-main {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
        color: var(--text);
        font-weight: 780;
        word-break: keep-all;
    }

    .route-arrow {
        color: var(--primary);
        flex: 0 0 auto;
    }

    .route-meta {
        margin-top: 8px;
        color: var(--muted);
        font-size: 0.79rem;
    }

    /* Result card is intentionally calm (ivory -> pale sage) so it doesn't fight
       the beige mood; the seat-probability tier color lives on the number/status
       text instead (see _seat_tier in the Python code) */
    .result-hero {
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        padding: 18px;
        margin: 14px 0;
        color: var(--text);
        background: linear-gradient(135deg, var(--surface), var(--accent-soft));
        box-shadow: var(--shadow);
    }

    .result-hero .label {
        font-size: 0.82rem;
        font-weight: 720;
        color: var(--text-soft);
    }

    .result-hero .value {
        font-size: 2.4rem;
        font-weight: 900;
        line-height: 1.05;
        margin-top: 5px;
    }

    .result-hero .copy {
        margin-top: 10px;
        font-size: 0.94rem;
        line-height: 1.45;
        font-weight: 600;
        color: var(--text-soft);
    }

    .metric-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin-bottom: 14px;
    }

    /* deliberately quieter than .result-hero (surface-soft, not surface) so the
       main probability card stays the visual anchor */
    .metric-card {
        min-height: 102px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 13px;
        background: var(--surface-soft);
        box-shadow: var(--shadow);
    }

    .metric-label {
        color: var(--muted);
        font-size: 0.76rem;
        margin-bottom: 7px;
    }

    .metric-value {
        color: var(--text);
        font-size: 1.34rem;
        font-weight: 850;
        line-height: 1.16;
        overflow-wrap: anywhere;
    }

    .metric-note {
        margin-top: 6px;
        color: var(--muted);
        font-size: 0.72rem;
        line-height: 1.3;
    }

    .data-note {
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 11px 13px;
        margin: 12px 0 14px;
        background: var(--surface-strong);
        color: var(--text-soft);
        font-size: 0.78rem;
        line-height: 1.48;
    }

    .saved-row {
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 13px;
        margin-bottom: 10px;
        background: var(--surface);
        box-shadow: var(--shadow);
    }

    .saved-title {
        color: var(--text);
        font-weight: 780;
    }

    .saved-meta {
        color: var(--muted);
        font-size: 0.78rem;
        margin-top: 5px;
    }

    .empty-state {
        border: 1px dashed var(--border);
        border-radius: var(--radius);
        padding: 22px 16px;
        text-align: center;
        background: rgba(59, 42, 31, 0.03);
    }

    .empty-title {
        color: var(--text-soft);
        font-weight: 720;
        margin-bottom: 4px;
    }

    .empty-desc {
        color: var(--muted);
        font-size: 0.82rem;
        line-height: 1.5;
    }

    .bottom-nav {
        position: fixed;
        left: 50%;
        bottom: 12px;
        transform: translateX(-50%);
        width: min(calc(100vw - 28px), 430px);
        z-index: 999;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: rgba(255, 250, 244, 0.92);
        box-shadow: 0 12px 30px rgba(59, 42, 31, 0.16);
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        overflow: hidden;
        backdrop-filter: blur(16px);
    }

    .bottom-nav div {
        padding: 9px 4px 8px;
        text-align: center;
        color: var(--muted);
        font-size: 0.72rem;
        font-weight: 720;
    }

    .bottom-nav .active {
        color: var(--primary);
        background: var(--primary-soft);
    }

    div[data-testid="stRadio"] label,
    div[data-testid="stSelectbox"] label,
    div[data-testid="stTextInput"] label,
    div[data-testid="stTimeInput"] label {
        color: var(--text);
        font-size: 0.8rem;
    }

    /* label-to-input gap, tightened from the default ~4px so the form reads denser */
    div[data-testid="stWidgetLabel"] {
        margin-bottom: 2px !important;
    }

    /* Transport toggle: reskin the plain st.radio into a segmented button
       group. Logic/values are untouched (see format_func in the Python code
       below) -- this only changes how the existing radiogroup is painted.
       Streamlit sizes this widget's container to width:fit-content by
       default, so it's forced to fill the row explicitly. */
    div[data-testid="stElementContainer"]:has(> div[data-testid="stRadio"]) {
        width: 100% !important;
    }

    div[data-testid="stRadio"] {
        width: 100%;
        margin-bottom: 4px;
    }

    div[data-testid="stRadio"] div[role="radiogroup"] {
        display: flex;
        width: 100%;
        gap: 6px;
        background: var(--surface-strong);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 5px;
        box-shadow: var(--shadow);
    }

    div[data-testid="stRadio"] label[data-baseweb="radio"] {
        flex: 1 1 0;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        min-height: 44px;
        padding: 8px 10px;
        border-radius: var(--radius-sm);
        cursor: pointer;
        color: var(--text-soft);
        font-weight: 780;
        white-space: nowrap;
        transition: background 0.15s ease, color 0.15s ease;
    }

    div[data-testid="stRadio"] label[data-baseweb="radio"] p {
        margin: 0;
        white-space: nowrap;
    }

    /* the native radio dot isn't needed once the whole label acts as the button */
    div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {
        display: none;
    }

    /* unselected = pale beige (inherited from the track), hover = soft caramel tint */
    div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {
        background: var(--primary-soft);
        color: var(--text);
    }

    /* selected = solid caramel-brown with ivory text, per the design brief */
    div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
        background: var(--primary);
        color: var(--surface);
    }

    div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:focus-visible) {
        outline: 2px solid var(--accent);
        outline-offset: 2px;
    }

    /* Input form card: groups 출발/도착/시간 + CTA into one visually distinct
       panel, warm ivory per the design brief. */
    div[data-testid="stForm"] {
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        padding: 18px 16px 20px;
        background: var(--surface-soft);
        box-shadow: var(--shadow);
    }

    .stButton > button,
    .stFormSubmitButton > button {
        min-height: 48px;
        border-radius: var(--radius-sm);
        border: 0;
        background: var(--primary);
        color: var(--surface);
        font-weight: 850;
        width: 100%;
        transition: background 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
    }

    .stButton > button:hover,
    .stFormSubmitButton > button:hover {
        background: var(--primary-dark);
        color: var(--surface);
        border: 0;
        transform: translateY(-2px);
    }

    .stButton > button:active,
    .stFormSubmitButton > button:active {
        transform: translateY(0);
    }

    /* primary CTA: bigger + a soft glow so it reads as the one clear next step */
    .stFormSubmitButton > button {
        min-height: 54px;
        font-size: 1.02rem;
        box-shadow: var(--shadow-cta);
    }

    .stFormSubmitButton > button:hover {
        box-shadow: 0 18px 34px rgba(95, 61, 40, 0.38);
    }

    .stTextInput input,
    .stSelectbox div[data-baseweb="select"] > div,
    .stTimeInput div[data-baseweb="select"] > div {
        border-radius: var(--radius-sm);
        border-color: var(--border);
        background: var(--surface);
        color: var(--text);
    }

    /* focus feedback: sage-green ring, distinct from the caramel-brown action color */
    .stTextInput input:focus {
        border-color: var(--accent);
        box-shadow: 0 0 0 3px var(--accent-soft);
        outline: none;
    }

    .stSelectbox div[data-baseweb="select"]:focus-within > div,
    .stTimeInput div[data-baseweb="select"]:focus-within > div {
        border-color: var(--accent);
        box-shadow: 0 0 0 3px var(--accent-soft);
    }

    /* time_input renders as a baseweb select (not a native <input type="time">),
       so its visible "18:30" text needs the same treatment explicitly */
    .stTimeInput [data-testid="stTimeInputTimeDisplay"] {
        color: var(--text);
    }

    /* unify input/select/time-input heights so the form's rows line up */
    .stSelectbox div[data-baseweb="select"] > div:first-child,
    .stTimeInput div[data-baseweb="select"] > div:first-child,
    .stTextInput input {
        min-height: 46px;
    }

    /* select caret recolored to match the brown-toned palette */
    .stSelectbox svg,
    .stTimeInput svg {
        fill: var(--muted) !important;
    }

    @media (max-width: 380px) {
        .metric-grid {
            grid-template-columns: 1fr;
        }
        .result-hero .value {
            font-size: 2rem;
        }
        .hero {
            padding: 18px 16px 20px;
        }
        .brand-icon {
            font-size: 1.6rem;
        }
        .brand-name {
            font-size: 1.32rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


FALLBACK_STATIONS = [
    "강남역",
    "사당역",
    "잠실역",
    "홍대입구역",
    "서울역",
    "신도림역",
    "건대입구역",
    "시청역",
    "교대역",
    "을지로입구역",
]

# 역 -> 대표 호선 라벨 (Demo 모드 폴백 — 인증키 없이도 호선을 보여주기 위함).
# 실데이터가 있을 때는 예측 결과의 노선명을 우선 쓰고, 여기 없는 역은 이 표로 보완한다.
STATION_LINE_MAP = {
    "강남역": "2호선",
    "사당역": "2호선/4호선",
    "잠실역": "2호선/8호선",
    "홍대입구역": "2호선/공항철도/경의중앙선",
    "서울역": "1호선/4호선/공항철도/경의중앙선",
    "신도림역": "1호선/2호선",
    "건대입구역": "2호선/7호선",
    "시청역": "1호선/2호선",
    "교대역": "2호선/3호선",
    "을지로입구역": "2호선",
    "역삼역": "2호선",
    "삼성역": "2호선",
    "선릉역": "2호선/수인분당선",
    "신림역": "2호선",
    "서울대입구역": "2호선",
    "왕십리역": "2호선/5호선/경의중앙선/수인분당선",
    "구로디지털단지역": "2호선",
    "신촌역": "2호선",
    "고속터미널역": "3호선/7호선/9호선",
    "동대문역사문화공원역": "2호선/4호선/5호선",
}

# 버스 모드에서 고를 수 있는 대표 버스 번호(직접 입력도 가능).
BUS_NUMBER_OPTIONS = ["146번", "341번", "740번", "360번", "401번", "직접 입력"]

# 추천 시연 경로 — 발표에서 버튼 한 번으로 세팅.
DEMO_ROUTES = [
    {
        "label": "🚇 2호선 강남→사당 18:30",
        "transport": "지하철",
        "dep": "강남역",
        "arr": "사당역",
        "bus_no": "",
        "time": time(18, 30),
    },
    {
        "label": "🚇 2호선 잠실→강남 22:00",
        "transport": "지하철",
        "dep": "잠실역",
        "arr": "강남역",
        "bus_no": "",
        "time": time(22, 0),
    },
    {
        "label": "🚌 146번 강남→사당 18:30",
        "transport": "버스",
        "dep": "강남역10번출구",
        "arr": "사당역4번출구",
        "bus_no": "146번",
        "time": time(18, 30),
    },
]


def _line_label(station: str, real_line: Optional[str] = None) -> Optional[str]:
    """역의 대표 호선 라벨. 표에 있으면 그 값을, 없으면 실데이터 노선명을 쓴다."""
    label = STATION_LINE_MAP.get(station)
    if label:
        return label
    return real_line


def _direction_label(arr_station: str) -> str:
    """도착역 기준 방면 문구 — '사당역' -> '사당 방면'."""
    name = (arr_station or "").strip()
    if name.endswith("역") and len(name) > 1:
        name = name[:-1]
    return f"{name} 방면" if name else ""


def _seat_tier(pct: float) -> tuple[str, str]:
    """좌석 확률 단계 — 쉬운 상태 문구 + 어울리는 강조 색."""
    if pct <= 30:
        return "앉기 어려운 편이에요", "var(--danger)"
    if pct <= 60:
        return "앉을 수도 있어요", "var(--warning)"
    return "앉기 좋아요", "var(--accent)"


def _get_auth_key(name: str) -> Optional[str]:
    try:
        return st.secrets.get("seoul_api", {}).get(name)
    except Exception:
        return None


def _default_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


# ------------------------------------------------------------------------
# 탭 기반 앱 구조 (홈 / 경로 / 예측 / MY)
# ------------------------------------------------------------------------

# 보조/내비 버튼 색상: primary=캐러멜(활성 강조), secondary=연한 베이지(비활성)
st.markdown(
    """
    <style>
    .stButton > button[kind="secondary"] {
        background: var(--surface-strong);
        color: var(--text-soft);
        border: 1px solid var(--border);
    }
    .stButton > button[kind="secondary"]:hover {
        background: var(--primary-soft);
        color: var(--text);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

CONGESTION_AUTH_KEY = _get_auth_key("subway_congestion_key")
BUS_RIDERSHIP_AUTH_KEY = _get_auth_key("bus_ridership_key")
SUBWAY_RIDERSHIP_AUTH_KEY = _get_auth_key("subway_ridership_key")
station_options = seoul_api.get_station_options(CONGESTION_AUTH_KEY) or FALLBACK_STATIONS

TABS = [("홈", "🏠"), ("경로", "🗺️"), ("예측", "📊"), ("MY", "👤")]

IS_REAL_MODE = bool(CONGESTION_AUTH_KEY)
DATA_MODE_TEXT = "실데이터 모드" if IS_REAL_MODE else "Demo 모드(예상치)"
DATA_MODE_COLOR = "var(--accent)" if IS_REAL_MODE else "var(--warning)"

_SESSION_DEFAULTS = {
    "active_tab": "홈",
    "saved_routes": [],
    "selected_route": None,
    "logged_in": False,
    "user_email": "",
    "notify_on": False,
    "congestion_display": "퍼센트",
    "seat_display": "퍼센트",
    "ui_transport": "지하철",
    "ui_dep_subway": "강남역",
    "ui_arr_subway": "사당역",
    "ui_dep_bus": "강남역10번출구",
    "ui_arr_bus": "사당역4번출구",
    "ui_bus_no": "146번",
    "ui_time": time(18, 30),
}
for _k, _v in _SESSION_DEFAULTS.items():
    st.session_state.setdefault(_k, _v)

for _key, _fb in (("ui_dep_subway", "강남역"), ("ui_arr_subway", "사당역")):
    if st.session_state[_key] not in station_options:
        st.session_state[_key] = station_options[_default_index(station_options, _fb)]


def _go(tab: str) -> None:
    st.session_state.active_tab = tab
    st.rerun()


def _select_route(transport, dep, arr, dep_time, bus_no="") -> None:
    st.session_state.selected_route = {
        "transport": transport,
        "dep": dep,
        "arr": arr,
        "dep_time": dep_time,
        "bus_no": bus_no,
    }
    st.session_state.active_tab = "예측"
    st.rerun()


def _route_headline(transport, dep, arr, bus_no, is_real, data_line):
    if transport == "지하철":
        line_label = _line_label(dep, data_line if is_real else None)
        prefix = (
            f'<span style="color:var(--primary); font-weight:800;">{escape(line_label)}</span> '
            if line_label else ""
        )
        head = f'{prefix}{escape(dep)} <span class="route-arrow">→</span> {escape(arr)}'
        sub = _direction_label(arr)
        saved = f"{line_label + ' ' if line_label else ''}{dep} → {arr}"
    else:
        bh = f"{bus_no} 버스" if bus_no else "버스"
        head = f'<span style="color:var(--primary); font-weight:800;">{escape(bh)}</span>'
        sub = f"{dep} → {arr}"
        saved = f"{bh} · {dep} → {arr}"
    return head, sub, saved


def _compute_prediction(route: dict) -> dict:
    transport = route["transport"]
    dep = route["dep"]
    arr = route["arr"]
    dep_time = route["dep_time"]
    bus_no = route.get("bus_no", "")
    real = None
    if transport == "지하철":
        real = seoul_api.get_real_congestion_series(
            CONGESTION_AUTH_KEY, dep, dep_time.hour, dep_time.minute, list(range(0, 65, 5))
        )
    real_pct = tuple(real["congestion_pct"]) if real else None
    real_line = real["line"] if real else None
    df, wait_spot, is_real, data_line = build_prediction(
        MOBILE_PRESET, transport, dep, arr, dep_time.hour, dep_time.minute, real_pct, real_line
    )
    current_congestion = float(df.iloc[0]["congestion_pct"])
    current_seat_prob = float(df.iloc[0]["seat_prob_pct"])
    level_label, level_color = congestion_level_color(current_congestion)
    seat_status, seat_color = _seat_tier(current_seat_prob)
    fut = df[(df["minutes_offset"] > 0) & (df["minutes_offset"] <= 30)]
    best = fut.loc[fut["seat_prob_pct"].idxmax()]
    return {
        "transport": transport, "dep": dep, "arr": arr, "dep_time": dep_time, "bus_no": bus_no,
        "df": df, "wait_spot": wait_spot, "is_real": is_real, "data_line": data_line,
        "current_congestion": current_congestion, "current_seat_prob": current_seat_prob,
        "level_label": level_label, "level_color": level_color,
        "seat_status": seat_status, "seat_color": seat_color,
        "best_offset": int(best["minutes_offset"]),
        "best_prob": float(best["seat_prob_pct"]),
        "best_time_label": str(best["time_label"]),
    }


def _render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="brand-lockup">
                <span class="brand-icon" aria-hidden="true">🪑</span>
                <div class="brand-text">
                    <span class="brand-name">오늘좌석</span>
                    <span class="brand-tagline">퇴근길 좌석 예측 서비스</span>
                </div>
            </div>
            <p class="hero-desc">
                퇴근길 지하철·버스 혼잡도를 분석해 가장 앉기 좋은 시간과 위치를 추천해드려요.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_topbar(title: str) -> None:
    st.markdown(
        f'''
        <div class="hero" style="padding:14px 16px; margin-bottom:16px;">
            <div class="brand-lockup">
                <span class="brand-icon" style="font-size:1.4rem;">🪑</span>
                <div class="brand-text">
                    <span class="brand-name" style="font-size:1.15rem;">오늘좌석</span>
                    <span class="brand-tagline">{escape(title)}</span>
                </div>
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


def _render_mode_badge() -> None:
    st.markdown(
        f'<div class="data-note">데이터 모드 · '
        f'<b style="color:{DATA_MODE_COLOR};">{DATA_MODE_TEXT}</b></div>',
        unsafe_allow_html=True,
    )


def _render_legend() -> None:
    st.markdown(
        """
        <div class="data-note">
            <b>실시간 도착정보</b> — 열차·버스가 몇 분 뒤 오는지(사실).<br/>
            <b>예상 혼잡도</b> — 시간대 통계로 추정한 붐빔 정도.<br/>
            <b>예상 좌석 확률</b> — 혼잡도로 유도한 <b>추정치</b>(실제 좌석 수 아님).<br/>
            <b>참고용 통계</b> — 과거 하루 승하차 등 집계 데이터.
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_saved_routes() -> None:
    st.markdown('<div class="section-title">저장한 경로</div>', unsafe_allow_html=True)
    saved_routes = st.session_state.get("saved_routes", [])
    if not saved_routes:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-title">아직 저장한 경로가 없어요</div>'
            '<div class="empty-desc">예측 화면에서 “이 경로 저장”을 누르면 여기에 모여요.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return
    for route in saved_routes[-5:][::-1]:
        title = route.get("label") or f'{route["dep"]} → {route["arr"]}'
        st.markdown(
            f'''
            <div class="saved-row">
                <div class="saved-title">{escape(title)}</div>
                <div class="saved-meta">{escape(route["transport"])} · {escape(route["time"])} · 예상 좌석 확률 {route["prob"]:.0f}%</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )


# --------------------------- 탭 1: 홈 ---------------------------
def _render_home() -> None:
    _render_hero()
    _render_mode_badge()

    st.markdown('<div class="section-title">빠른 시작</div>', unsafe_allow_html=True)
    if st.button("🚇 지하철 좌석 예측", use_container_width=True, key="qs_subway", type="primary"):
        st.session_state.ui_transport = "지하철"
        _go("경로")
    if st.button("🚌 버스 좌석 예측", use_container_width=True, key="qs_bus"):
        st.session_state.ui_transport = "버스"
        _go("경로")
    if st.button("⭐ 추천 시연 경로", use_container_width=True, key="qs_demo"):
        _go("경로")

    st.markdown('<div class="section-title">이 앱의 정보 구분</div>', unsafe_allow_html=True)
    _render_legend()


# --------------------------- 탭 2: 경로 ---------------------------
def _render_route() -> None:
    _render_topbar("경로 선택")

    st.markdown('<div class="section-title">교통수단</div>', unsafe_allow_html=True)
    transport = st.radio(
        "교통수단",
        ["지하철", "버스"],
        horizontal=True,
        label_visibility="collapsed",
        key="ui_transport",
        format_func=lambda option: f"🚇 {option}" if option == "지하철" else f"🚌 {option}",
    )

    bus_number = ""
    if transport == "지하철":
        dep_station = st.selectbox("출발역", station_options, key="ui_dep_subway")
        arr_station = st.selectbox("도착역", station_options, key="ui_arr_subway")
        ll = _line_label(dep_station)
        if ll:
            st.markdown(
                f'<div class="data-note">대표 호선 · '
                f'<b style="color:var(--primary);">{escape(ll)}</b></div>',
                unsafe_allow_html=True,
            )
    else:
        dep_station = st.text_input("출발 정류장", key="ui_dep_bus")
        arr_station = st.text_input("도착 정류장", key="ui_arr_bus")
        bus_number = st.selectbox("버스 번호", BUS_NUMBER_OPTIONS, key="ui_bus_no")
        if bus_number == "직접 입력":
            bus_number = st.text_input("버스 번호 직접 입력", value="146번", key="ui_bus_no_custom")

    dep_time = st.time_input("출발 시간", key="ui_time")

    if st.button("이 경로로 예측하기 →", use_container_width=True, type="primary", key="route_go"):
        _select_route(transport, dep_station, arr_station, dep_time, bus_number)

    st.markdown('<div class="section-title">추천 경로</div>', unsafe_allow_html=True)
    for i, r in enumerate(DEMO_ROUTES):
        head, sub, _ = _route_headline(r["transport"], r["dep"], r["arr"], r["bus_no"], False, None)
        st.markdown(
            f'''
            <div class="route-strip">
                <div class="route-main"><span>{head}</span></div>
                <div class="route-meta">{escape(sub)} · {r["time"].strftime("%H:%M")}</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )
        if st.button("이 경로로 예측하기", use_container_width=True, key=f"demo_go_{i}"):
            _select_route(r["transport"], r["dep"], r["arr"], r["time"], r["bus_no"])


# --------------------------- 탭 3: 예측 ---------------------------
def _render_predict() -> None:
    _render_topbar("예측 결과")
    route = st.session_state.selected_route
    if not route:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-title">선택된 경로가 없어요</div>'
            '<div class="empty-desc">경로 탭에서 먼저 경로를 선택해 주세요.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("경로 선택하러 가기", use_container_width=True, type="primary", key="predict_goroute"):
            _go("경로")
        return

    p = _compute_prediction(route)
    head, sub, saved_label = _route_headline(
        p["transport"], p["dep"], p["arr"], p["bus_no"], p["is_real"], p["data_line"]
    )
    source_text = f"실데이터 · {p['data_line']}" if p["is_real"] else "Demo 모드 · 예상치"
    source_color = "var(--accent)" if p["is_real"] else "var(--warning)"

    st.markdown(
        f'''
        <div class="route-strip">
            <div class="route-main"><span>{head}</span></div>
            <div class="route-meta">{escape(sub)} · {p["dep_time"].strftime("%H:%M")} · <span style="color:{source_color};">{escape(source_text)}</span></div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    # 실시간 도착정보 영역 — 데모에서는 실제 연동을 하지 않으므로 가짜 값을 넣지 않는다.
    st.markdown('<div class="section-title">실시간 도착정보</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="data-note">데모 화면에서는 실시간 도착정보를 연동하지 않습니다. '
        '백엔드 <b>/realtime/subway/arrivals</b>·<b>/realtime/bus/arrivals</b> 로 제공될 예정입니다. '
        '아래 값은 <b>예상</b> 혼잡도·좌석 확률(추정치)입니다.</div>',
        unsafe_allow_html=True,
    )

    if p["best_prob"] - p["current_seat_prob"] >= 5:
        hero_copy = f'{p["best_offset"]}분 뒤 {p["best_time_label"]}에 타면 더 유리합니다.'
    else:
        hero_copy = "지금 타도 좋은 구간입니다."

    if st.session_state.seat_display == "퍼센트":
        seat_main = f'{p["current_seat_prob"]:.0f}%'
        seat_copy = (
            f'<span style="color:{p["seat_color"]};font-weight:800;">{escape(p["seat_status"])}</span>'
            f' · {escape(hero_copy)}'
        )
    else:
        seat_main = escape(p["seat_status"])
        seat_copy = f'앉아서 갈 확률 약 {p["current_seat_prob"]:.0f}% · {escape(hero_copy)}'

    st.markdown('<div class="section-title">예상 좌석 확률</div>', unsafe_allow_html=True)
    st.markdown(
        f'''
        <div class="result-hero">
            <div class="label">앉아서 갈 확률(예상)</div>
            <div class="value" style="color:{p["seat_color"]};">{seat_main}</div>
            <div class="copy">{seat_copy}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    if st.session_state.congestion_display == "퍼센트":
        cong_main = f'{p["current_congestion"]:.0f}%'
        cong_note = escape(p["level_label"])
    else:
        cong_main = escape(p["level_label"])
        cong_note = f'{p["current_congestion"]:.0f}%'

    st.markdown(
        f'''
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">예상 혼잡도</div>
                <div class="metric-value" style="color:{p["level_color"]};">{cong_main}</div>
                <div class="metric-note">{cong_note}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">추천 대기 위치</div>
                <div class="metric-value" style="color:var(--accent);">{escape(p["wait_spot"])}</div>
                <div class="metric-note">{p["best_offset"]}분 뒤 기준</div>
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="data-note">추천 탑승 시간 · '
        f'<b>{p["best_time_label"]}</b> ({p["best_offset"]}분 뒤) · '
        f'그때 예상 좌석 확률 <b>{p["best_prob"]:.0f}%</b></div>',
        unsafe_allow_html=True,
    )

    df = p["df"]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["minutes_offset"], y=df["seat_prob_pct"], mode="lines+markers",
            name="좌석 확률", line=dict(color="#7a8f63", width=3), marker=dict(size=7),
            fill="tozeroy", fillcolor="rgba(122, 143, 99, 0.14)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["minutes_offset"], y=df["congestion_pct"], mode="lines",
            name="혼잡도", line=dict(color="#b85c38", width=2, dash="dot"),
        )
    )
    fig.add_vline(x=p["best_offset"], line_dash="dot", line_color="#5f3d28")
    fig.update_layout(
        template="plotly_white", height=245, margin=dict(l=6, r=6, t=18, b=8),
        paper_bgcolor="#f6efe7", plot_bgcolor="#f6efe7", font=dict(color="#3b2a1f"),
        legend=dict(orientation="h", y=1.14, x=0, font=dict(size=11)),
        xaxis=dict(title=None, tickmode="array", tickvals=df["minutes_offset"][::2],
                   ticktext=df["time_label"][::2], gridcolor="#e1d2c1"),
        yaxis=dict(title=None, range=[0, 105], gridcolor="#e1d2c1"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    c1, c2 = st.columns(2)
    with c1:
        if st.button("이 경로 저장", use_container_width=True, key="predict_save", type="primary"):
            st.session_state.saved_routes.append(
                {
                    "transport": p["transport"], "dep": p["dep"], "arr": p["arr"],
                    "label": saved_label, "time": p["dep_time"].strftime("%H:%M"),
                    "prob": p["current_seat_prob"],
                }
            )
            st.toast("저장되었습니다")
    with c2:
        if st.button("다른 경로 선택", use_container_width=True, key="predict_change"):
            _go("경로")


# --------------------------- 탭 4: MY ---------------------------
def _render_my() -> None:
    _render_topbar("마이페이지")

    if not st.session_state.logged_in:
        st.markdown('<div class="section-title">로그인 (데모)</div>', unsafe_allow_html=True)
        email = st.text_input("이메일", key="login_email", placeholder="you@example.com")
        if st.button("로그인 데모", use_container_width=True, type="primary", key="login_btn"):
            st.session_state.logged_in = True
            st.session_state.user_email = email.strip() or "guest@demo.com"
            st.rerun()
        st.markdown(
            '<div class="data-note">발표용 목업 로그인입니다. 실제 인증은 하지 않습니다.</div>',
            unsafe_allow_html=True,
        )
        return

    saved = st.session_state.saved_routes
    fav = "-"
    if saved:
        counts: dict = {}
        for r in saved:
            counts[r["transport"]] = counts.get(r["transport"], 0) + 1
        fav = max(counts, key=counts.get)

    st.markdown(
        f'''
        <div class="result-hero">
            <div class="label">내 계정</div>
            <div class="value" style="font-size:1.2rem; color:var(--primary);">{escape(st.session_state.user_email)}</div>
            <div class="copy">저장한 경로 {len(saved)}개 · 자주 타는 교통수단 {escape(fav)}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    _render_saved_routes()

    st.markdown('<div class="section-title">설정</div>', unsafe_allow_html=True)
    _render_mode_badge()
    st.toggle("알림 받기", key="notify_on")
    st.radio("혼잡도 표시 방식", ["퍼센트", "등급"], horizontal=True, key="congestion_display")
    st.radio("좌석 확률 표시 방식", ["퍼센트", "상태"], horizontal=True, key="seat_display")

    with st.expander("데이터 출처 보기"):
        st.markdown(
            "- 지하철 혼잡도: 서울교통공사 지하철혼잡도정보(subwConfusion)\n"
            "- 지하철/버스 승하차: CardSubwayStatsNew · CardBusStatisticsServiceNew (참고용 통계)\n"
            "- 실시간 도착(예정): realtimeStationArrival · getStationByUid\n\n"
            "좌석 확률은 혼잡도로부터 유도한 **예상치**이며 실제 좌석 수가 아닙니다."
        )

    if st.button("저장 경로 초기화", use_container_width=True, key="reset_saved"):
        st.session_state.saved_routes = []
        st.toast("저장 경로를 비웠습니다")
        st.rerun()
    if st.button("로그아웃", use_container_width=True, key="logout_btn"):
        st.session_state.logged_in = False
        st.rerun()


# --------------------------- 하단 내비 (클릭 가능) ---------------------------
def _render_bottom_nav() -> None:
    st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)
    cols = st.columns(len(TABS))
    for col, (name, icon) in zip(cols, TABS):
        with col:
            is_active = st.session_state.active_tab == name
            if st.button(
                f"{icon} {name}",
                key=f"nav_{name}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                if not is_active:
                    st.session_state.active_tab = name
                    st.rerun()


# --------------------------- 메인 디스패치 ---------------------------
_TAB_RENDERERS = {
    "홈": _render_home,
    "경로": _render_route,
    "예측": _render_predict,
    "MY": _render_my,
}
_TAB_RENDERERS.get(st.session_state.active_tab, _render_home)()
_render_bottom_nav()
