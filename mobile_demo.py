"""Streamlit mobile-style demo for the seat predictor."""

from datetime import date, datetime, time, timedelta
from hashlib import sha256
from html import escape
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import seoul_api


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

SUBWAY_DOOR_OPTIONS = [f"{car}-{door}번 문" for car in range(1, 10) for door in range(1, 5)]
BUS_POSITION_OPTIONS = [
    "앞문 뒤 좌석",
    "중간문 근처",
    "뒷문 앞 2인석",
    "앞쪽 1인석",
]


def _get_auth_key(name: str) -> Optional[str]:
    try:
        return st.secrets.get("seoul_api", {}).get(name)
    except Exception:
        return None


def _default_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def _seed_from(*parts: object) -> int:
    digest = sha256("|".join(map(str, parts)).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32)


def _congestion_level(pct: float) -> tuple[str, str]:
    if pct >= 80:
        return "매우 혼잡", "var(--danger)"
    if pct >= 60:
        return "혼잡", "var(--warning)"
    if pct >= 40:
        return "보통", "var(--primary)"
    return "여유", "var(--accent)"


def _seat_tier(pct: float) -> tuple[str, str]:
    """Seat-probability tier: plain-language status + its matching accent color."""
    if pct <= 30:
        return "앉기 어려운 편이에요", "var(--danger)"
    if pct <= 60:
        return "앉을 수도 있어요", "var(--warning)"
    return "앉기 좋아요", "var(--accent)"


@st.cache_data(show_spinner=False)
def _build_prediction(
    transport: str,
    dep_station: str,
    arr_station: str,
    dep_hour: int,
    dep_minute: int,
    real_congestion_pct: Optional[tuple[float, ...]] = None,
    real_line: Optional[str] = None,
) -> tuple[pd.DataFrame, str, bool, Optional[str]]:
    seed = _seed_from(transport, dep_station.lower(), arr_station.lower(), dep_hour, dep_minute)
    rng = np.random.default_rng(seed)

    minutes_offset = np.arange(0, 65, 5)
    base_dt = datetime.combine(date.today(), time(dep_hour, dep_minute))
    time_labels = [(base_dt + timedelta(minutes=int(m))).strftime("%H:%M") for m in minutes_offset]

    if real_congestion_pct is not None:
        congestion_curve = np.array(real_congestion_pct, dtype=float)
        base_congestion = float(congestion_curve[0])
        is_real = True
    else:
        hour_decimal = dep_hour + dep_minute / 60
        rush_center = 18.4 if transport == "지하철" else 18.1
        rush_width = 1.35 if transport == "지하철" else 1.55
        rush_intensity = np.exp(-0.5 * ((hour_decimal - rush_center) / rush_width) ** 2)
        base_congestion = float(np.clip(32 + rush_intensity * 58 + rng.normal(0, 4), 12, 98))
        decay = np.linspace(0, 1, len(minutes_offset))
        congestion_curve = base_congestion * (1 - 0.48 * decay) + rng.normal(0, 2.4, len(minutes_offset))
        congestion_curve = np.clip(congestion_curve, 8, 100)
        is_real = False

    seat_base = float(np.clip(104 - min(base_congestion, 100) - rng.uniform(7, 13), 3, 64))
    seat_target = float(np.clip(seat_base + rng.uniform(28, 42), seat_base + 8, 96))
    seat_curve = seat_base + (seat_target - seat_base) / (1 + np.exp(-0.18 * (minutes_offset - 16)))
    seat_curve += rng.normal(0, 2.0, len(minutes_offset))
    seat_curve = np.clip(seat_curve, 1, 98)

    df = pd.DataFrame(
        {
            "minutes_offset": minutes_offset,
            "time_label": time_labels,
            "congestion_pct": congestion_curve.round(1),
            "seat_prob_pct": seat_curve.round(1),
        }
    )

    wait_spot = rng.choice(SUBWAY_DOOR_OPTIONS if transport == "지하철" else BUS_POSITION_OPTIONS)
    return df, wait_spot, is_real, real_line


def _render_bottom_nav(active: str = "예측") -> None:
    items = ["홈", "예측", "저장", "설정"]
    html = "".join(
        f'<div class="{"active" if item == active else ""}">{escape(item)}</div>'
        for item in items
    )
    st.markdown(f'<div class="bottom-nav">{html}</div>', unsafe_allow_html=True)


def _render_saved_routes() -> None:
    st.markdown('<div class="section-title">저장한 경로</div>', unsafe_allow_html=True)
    saved_routes = st.session_state.get("saved_routes", [])
    if not saved_routes:
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-title">아직 저장한 경로가 없어요.</div>
                <div class="empty-desc">자주 타는 경로를 저장하면 다음에 더 빠르게 예측할 수 있어요.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for route in saved_routes[-5:][::-1]:
        st.markdown(
            f"""
            <div class="saved-row">
                <div class="saved-title">{escape(route["dep"])} <span style="color:var(--primary);">→</span> {escape(route["arr"])}</div>
                <div class="saved-meta">{escape(route["transport"])} · {escape(route["time"])} · 좌석 확률 {route["prob"]:.0f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


CONGESTION_AUTH_KEY = _get_auth_key("subway_congestion_key")
BUS_RIDERSHIP_AUTH_KEY = _get_auth_key("bus_ridership_key")
SUBWAY_RIDERSHIP_AUTH_KEY = _get_auth_key("subway_ridership_key")
station_options = seoul_api.get_station_options(CONGESTION_AUTH_KEY) or FALLBACK_STATIONS

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

if "saved_routes" not in st.session_state:
    st.session_state.saved_routes = []

st.markdown('<div class="section-title">교통수단</div>', unsafe_allow_html=True)
# format_func only changes the on-screen label (with emoji); the widget still
# returns the plain "지하철"/"버스" strings the rest of the app relies on.
transport = st.radio(
    "교통수단",
    ["지하철", "버스"],
    horizontal=True,
    label_visibility="collapsed",
    format_func=lambda option: f"🚇 {option}" if option == "지하철" else f"🚌 {option}",
)

with st.form("mobile_route_form"):
    if transport == "지하철":
        dep_station = st.selectbox("출발역", station_options, index=_default_index(station_options, "강남역"))
        arr_station = st.selectbox("도착역", station_options, index=_default_index(station_options, "사당역"))
    else:
        dep_station = st.text_input("출발 정류장", value="강남역10번출구")
        arr_station = st.text_input("도착 정류장", value="사당역4번출구")
    dep_time = st.time_input("출발 시간", value=time(18, 30))
    submitted = st.form_submit_button("좌석 예측하기 →")

if submitted or "mobile_inputs" not in st.session_state:
    st.session_state.mobile_inputs = (transport, dep_station, arr_station, dep_time)

transport, dep_station, arr_station, dep_time = st.session_state.mobile_inputs

real_congestion = None
if transport == "지하철":
    real_congestion = seoul_api.get_real_congestion_series(
        CONGESTION_AUTH_KEY,
        dep_station,
        dep_time.hour,
        dep_time.minute,
        list(range(0, 65, 5)),
    )

real_congestion_pct = tuple(real_congestion["congestion_pct"]) if real_congestion else None
real_line = real_congestion["line"] if real_congestion else None

df, wait_spot, is_real, data_line = _build_prediction(
    transport,
    dep_station,
    arr_station,
    dep_time.hour,
    dep_time.minute,
    real_congestion_pct,
    real_line,
)

current_congestion = float(df.iloc[0]["congestion_pct"])
current_seat_prob = float(df.iloc[0]["seat_prob_pct"])
level_label, level_color = _congestion_level(current_congestion)
seat_status, seat_color = _seat_tier(current_seat_prob)
future_window = df[(df["minutes_offset"] > 0) & (df["minutes_offset"] <= 30)]
best_row = future_window.loc[future_window["seat_prob_pct"].idxmax()]
best_offset = int(best_row["minutes_offset"])
best_prob = float(best_row["seat_prob_pct"])
best_time_label = str(best_row["time_label"])

source_text = f"실데이터 · {data_line}" if is_real else "Mock Data"
source_color = "var(--accent)" if is_real else "var(--warning)"

st.markdown(
    f"""
    <div class="route-strip">
        <div class="route-main">
            <span>{escape(dep_station)}</span>
            <span class="route-arrow">→</span>
            <span>{escape(arr_station)}</span>
        </div>
        <div class="route-meta">{escape(transport)} · {dep_time.strftime("%H:%M")} · <span style="color:{source_color};">{escape(source_text)}</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

if best_prob - current_seat_prob >= 5:
    hero_copy = f"{best_offset}분 뒤 {best_time_label}에 타면 더 유리합니다."
else:
    hero_copy = "지금 타도 좋은 구간입니다."

st.markdown(
    f"""
    <div class="result-hero">
        <div class="label">앉아서 갈 확률</div>
        <div class="value" style="color:{seat_color};">{current_seat_prob:.0f}%</div>
        <div class="copy"><span style="color:{seat_color};font-weight:800;">{escape(seat_status)}</span> · {escape(hero_copy)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-label">현재 혼잡도</div>
            <div class="metric-value" style="color:{level_color};">{current_congestion:.0f}%</div>
            <div class="metric-note">{escape(level_label)}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">추천 위치</div>
            <div class="metric-value" style="color:var(--accent);">{escape(wait_spot)}</div>
            <div class="metric-note">{best_offset}분 뒤 기준</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

ridership = None
if transport == "지하철" and SUBWAY_RIDERSHIP_AUTH_KEY:
    ridership = seoul_api.get_subway_ridership_stat(SUBWAY_RIDERSHIP_AUTH_KEY, dep_station)
elif transport == "버스" and BUS_RIDERSHIP_AUTH_KEY:
    with st.spinner("정류장 데이터를 불러오는 중"):
        ridership = seoul_api.get_bus_ridership_stat(BUS_RIDERSHIP_AUTH_KEY, dep_station)

if ridership:
    total = ridership["boarding"] + ridership["alighting"]
    target_label = "노선" if transport == "지하철" else "정류장"
    count = ridership.get("line_count", ridership.get("stop_count", 1))
    st.markdown(
        f"""
        <div class="data-note">
            {ridership["date"]} 기준 · {target_label} {count}개 합산 · 하루 이용객 약
            <b style="color:var(--text);">{total:,}명</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=df["minutes_offset"],
        y=df["seat_prob_pct"],
        mode="lines+markers",
        name="좌석 확률",
        line=dict(color="#7a8f63", width=3),  # sage green
        marker=dict(size=7),
        fill="tozeroy",
        fillcolor="rgba(122, 143, 99, 0.14)",
    )
)
fig.add_trace(
    go.Scatter(
        x=df["minutes_offset"],
        y=df["congestion_pct"],
        mode="lines",
        name="혼잡도",
        line=dict(color="#b85c38", width=2, dash="dot"),  # terracotta
    )
)
fig.add_vline(x=best_offset, line_dash="dot", line_color="#5f3d28")  # deep brown marker
fig.update_layout(
    template="plotly_white",
    height=245,
    margin=dict(l=6, r=6, t=18, b=8),
    paper_bgcolor="#f6efe7",
    plot_bgcolor="#f6efe7",
    font=dict(color="#3b2a1f"),
    legend=dict(orientation="h", y=1.14, x=0, font=dict(size=11)),
    xaxis=dict(
        title=None,
        tickmode="array",
        tickvals=df["minutes_offset"][::2],
        ticktext=df["time_label"][::2],
        gridcolor="#e1d2c1",
    ),
    yaxis=dict(title=None, range=[0, 105], gridcolor="#e1d2c1"),
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

if st.button("이 경로 저장"):
    st.session_state.saved_routes.append(
        {
            "transport": transport,
            "dep": dep_station,
            "arr": arr_station,
            "time": dep_time.strftime("%H:%M"),
            "prob": current_seat_prob,
        }
    )
    st.toast("저장되었습니다")

_render_saved_routes()

st.markdown(
    f"""
    <div class="section-title">설정</div>
    <div class="data-note">데이터 모드 · <b style="color:{source_color};">{escape(source_text)}</b></div>
    """,
    unsafe_allow_html=True,
)

_render_bottom_nav("예측")
