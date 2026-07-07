"""Streamlit mobile-style demo for the seat predictor."""

import base64
import random
from datetime import datetime, time, timedelta
from pathlib import Path
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

# ── 폰트: 둥근 한글 웹폰트(Jua / Gaegu — OFL 오픈 라이선스) ─────────────────
# · 온라인이면 Google Fonts 로 로드된다(데모 실행 시 인터넷 필요).
# · 인터넷 없이 쓰려면 assets/fonts/ 에 Jua-Regular / Gaegu-Bold (.woff2 또는 .ttf)를
#   넣으면 자동으로 base64 임베드되어 오프라인에서도 적용된다.
#   (내려받는 법: assets/fonts/README.md 참고. 파일이 없으면 시스템 폰트로 안전 폴백.)
_FONT_DIR = Path(__file__).parent / "assets" / "fonts"
_FONT_FILES = [("Jua", "Jua-Regular", 400), ("Gaegu", "Gaegu-Bold", 700)]
_FONT_EXT = {
    ".woff2": ("font/woff2", "woff2"),
    ".woff": ("font/woff", "woff"),
    ".ttf": ("font/ttf", "truetype"),
    ".otf": ("font/otf", "opentype"),
}


def _local_font_face_css() -> str:
    """assets/fonts/ 에 폰트 파일이 있으면 base64 @font-face 를 만들어 반환(없으면 빈 문자열)."""
    if not _FONT_DIR.exists():
        return ""
    out = []
    for family, base_name, weight in _FONT_FILES:
        for ext, (mime, fmt) in _FONT_EXT.items():
            fp = _FONT_DIR / f"{base_name}{ext}"
            if fp.exists():
                try:
                    b64 = base64.b64encode(fp.read_bytes()).decode("ascii")
                except Exception:
                    break
                out.append(
                    f"@font-face{{font-family:'{family}';font-style:normal;"
                    f"font-weight:{weight};font-display:swap;"
                    f"src:url(data:{mime};base64,{b64}) format('{fmt}');}}"
                )
                break
    return "\n".join(out)


st.markdown(
    "<style>\n"
    "@import url('https://fonts.googleapis.com/css2?family=Jua&family=Gaegu:wght@700&display=swap');\n"
    + _local_font_face_css()
    + "\n</style>",
    unsafe_allow_html=True,
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


# ======================================================================
# 자리각 — 모바일 데모 (홈 / 경로 / 예측 / MY)
# 브랜드 헤더는 전 탭 공통, 하단은 하트 모양 탭. 로직(예측·제보·포인트·리워드) 유지.
# ======================================================================

st.markdown(
    """
    <style>
    /* 데스크톱 배경 + 둥근 한글 폰트 스택(로컬/시스템 폰트, 없으면 sans-serif 폴백) */
    .stApp { background: #cdbca6; }
    html, body, .stApp, .stApp button, .stApp input, .stApp textarea, .stApp select,
    .brand-hero .big-name, .section-title, .metric-value, .result-hero .value {
        font-family: "Jua", "Gaegu", "MaruBuri", "NanumSquareRound", "Pretendard",
                     "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif !important;
    }

    /* 본문 컨테이너를 스마트폰 본체처럼 + 내부 세로 스크롤 */
    .block-container {
        max-width: 412px;
        height: 800px;
        max-height: 92vh;
        margin: 14px auto 18px;
        padding: 0 16px 16px !important;
        background: var(--bg);
        border: 1px solid rgba(59, 42, 31, 0.18);
        border-radius: 30px;
        box-shadow: 0 30px 70px rgba(59, 42, 31, 0.35);
        overflow-y: auto;
        overflow-x: hidden;
    }
    /* 폰 셸: 루트 세로 블록이 프레임 높이를 채우고, 스페이서가 하단 탭을 아래로 민다 */
    [data-testid="stVerticalBlock"]:has(.status-bar) { min-height: 100%; }
    [data-testid="stVerticalBlock"]:has(.status-bar) > div[data-testid="stElementContainer"]:has(.app-spacer) {
        flex: 1 1 auto;
        min-height: 8px;
    }
    .block-container::-webkit-scrollbar { width: 8px; }
    .block-container::-webkit-scrollbar-thumb { background: var(--border); border-radius: 8px; }

    /* 상단 상태바 */
    .status-bar {
        display: flex; justify-content: space-between; align-items: center;
        padding: 12px 4px 2px; color: var(--text-soft);
        font-size: 0.74rem; font-weight: 700; letter-spacing: 0.02em;
    }
    .status-bar .dots { letter-spacing: 2px; font-size: 0.6rem; }

    /* 전 탭 공통 브랜드 헤더(큰 자리각 + 랜덤 스티커, 컴팩트) */
    .brand-hero { display: flex; align-items: center; gap: 12px; padding: 6px 2px 10px; margin-bottom: 8px; border-bottom: 1px solid var(--border); }
    .brand-hero .big-name { font-size: 1.9rem; font-weight: 900; letter-spacing: -0.02em; color: var(--text); line-height: 1.04; }
    .brand-hero .big-tag { margin-top: 3px; color: var(--text-soft); font-size: 0.8rem; }
    .sticker { display: flex; flex-direction: column; align-items: center; gap: 2px; flex: 0 0 auto; }
    .sticker svg { display: block; width: 46px; height: 46px; }
    .sticker-cap { font-size: 0.62rem; font-weight: 800; color: var(--primary); background: var(--primary-soft); border-radius: 999px; padding: 1px 7px; white-space: nowrap; }

    /* 보조 버튼: 활성=캐러멜, 비활성=연한 베이지 (하단 하트 탭은 아래에서 별도 처리) */
    .stButton > button[kind="secondary"] {
        background: var(--surface-strong); color: var(--text-soft); border: 1px solid var(--border);
    }
    .stButton > button[kind="secondary"]:hover { background: var(--primary-soft); color: var(--text); }

    /* 하단 하트 탭 — 자체 SVG, 클릭 가능, 한 줄 고정 */
    div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-nav_"]) {
        flex-wrap: nowrap !important; gap: 4px !important; margin-top: 8px;
    }
    div[data-testid="stHorizontalBlock"]:has(div[class*="st-key-nav_"]) > div[data-testid="stColumn"] {
        width: 25% !important; flex: 1 1 0 !important; min-width: 0 !important;
    }
    div[class*="st-key-nav_"] button {
        position: relative !important;
        background-color: transparent !important;
        border: 0 !important; box-shadow: none !important;
        color: var(--primary) !important; font-weight: 800 !important; font-size: 0.8rem !important;
        min-height: 66px !important; padding-top: 4px !important;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 60'%3E%3Cpath d='M32 20 C30 7 8 7 8 24 C8 40 32 52 32 52 C32 52 56 40 56 24 C56 7 34 7 32 20 Z' fill='none' stroke='%238b5e3c' stroke-width='3'/%3E%3C/svg%3E") !important;
        background-repeat: no-repeat !important;
        background-position: center 44% !important;
        background-size: 58px 54px !important;
    }
    div[class*="st-key-nav_"] button:hover { color: var(--primary-dark) !important; }
    div[class*="st-key-nav_"] button[kind="primary"] {
        color: var(--primary-dark) !important;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 60'%3E%3Cpath d='M32 20 C30 7 8 7 8 24 C8 40 32 52 32 52 C32 52 56 40 56 24 C56 7 34 7 32 20 Z' fill='%23ead7c3' stroke='%235f3d28' stroke-width='4'/%3E%3C/svg%3E") !important;
    }
    div[class*="st-key-nav_"] button[kind="primary"]::after {
        content: ""; position: absolute; top: 8px; right: 27%;
        width: 5px; height: 5px; border-radius: 50%;
        background: var(--primary-soft);
        box-shadow: 6px -3px 0 0 var(--surface-strong), 11px 2px 0 0 var(--primary-soft);
        opacity: 0.95;
    }

    /* 모바일: 프레임 해제 + 자연 스크롤 */
    @media (max-width: 480px) {
        .block-container {
            max-width: 100%; height: auto; max-height: none; overflow: visible;
            margin: 0; border: 0; border-radius: 0; box-shadow: none; padding-bottom: 44px !important;
        }
        [data-testid="stVerticalBlock"]:has(.status-bar) { min-height: 0; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

CONGESTION_AUTH_KEY = _get_auth_key("subway_congestion_key")
BUS_RIDERSHIP_AUTH_KEY = _get_auth_key("bus_ridership_key")
SUBWAY_RIDERSHIP_AUTH_KEY = _get_auth_key("subway_ridership_key")
station_options = seoul_api.get_station_options(CONGESTION_AUTH_KEY) or FALLBACK_STATIONS

TABS = ["홈", "경로", "예측", "MY"]
TAB_SLUGS = {"홈": "home", "경로": "route", "예측": "predict", "MY": "my"}

IS_REAL_MODE = bool(CONGESTION_AUTH_KEY)
DATA_MODE_TEXT = "실데이터 모드" if IS_REAL_MODE else "데모 모드(예상치)"
DATA_MODE_COLOR = "var(--accent)" if IS_REAL_MODE else "var(--warning)"

SUBWAY_CROWD_LEVELS = ["매우 여유", "보통", "서 있기 가능", "서 있기 힘듦", "매우 혼잡"]
BUS_CROWD_LEVELS = ["좌석 많음", "좌석 조금 있음", "입석 가능", "혼잡", "만차 수준"]
SUBWAY_DIRECTIONS = ["상행", "하행"]
CROWD_TIME_BANDS = ["출근(07~09)", "오전(09~12)", "점심(12~14)", "오후(14~17)", "퇴근(17~20)", "야간(20~24)"]
REPORT_POINTS = 10
DEDUP_MINUTES = 5
FRESH_MINUTES = 20
REWARDS = [(100, "커피 쿠폰"), (200, "교통카드 포인트"), (300, "간식 쿠폰")]

# 자체 제작 스티커(저작권 무관, 외부 URL 없음) — 새로고침 시 랜덤 노출
STICKERS = [
    ('<svg width="60" height="60" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><rect x="8" y="10" width="48" height="30" rx="12" fill="#ead7c3" stroke="#8b5e3c" stroke-width="2"/><path d="M22 39 L19 50 L33 39 Z" fill="#ead7c3" stroke="#8b5e3c" stroke-width="2"/><circle cx="24" cy="24" r="2.6" fill="#3b2a1f"/><circle cx="40" cy="24" r="2.6" fill="#3b2a1f"/><path d="M24 30 q8 6 16 0" stroke="#8b5e3c" stroke-width="2.4" fill="none" stroke-linecap="round"/></svg>', "앉을 각?"),
    ('<svg width="60" height="60" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><rect x="19" y="12" width="26" height="22" rx="6" fill="#7a8f63"/><rect x="16" y="33" width="32" height="9" rx="3" fill="#8b5e3c"/><rect x="19" y="42" width="4" height="10" rx="2" fill="#8b5e3c"/><rect x="41" y="42" width="4" height="10" rx="2" fill="#8b5e3c"/><circle cx="28" cy="22" r="2" fill="#fffaf4"/><circle cx="37" cy="22" r="2" fill="#fffaf4"/><path d="M28 27 q4.5 3 9 0" stroke="#fffaf4" stroke-width="2" fill="none" stroke-linecap="round"/></svg>', "여기 앉아요"),
    ('<svg width="60" height="60" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><line x1="32" y1="6" x2="32" y2="24" stroke="#8b5e3c" stroke-width="3" stroke-linecap="round"/><circle cx="32" cy="40" r="15" fill="#fbf5ee" stroke="#8b5e3c" stroke-width="4"/><circle cx="27" cy="37" r="1.9" fill="#3b2a1f"/><circle cx="37" cy="37" r="1.9" fill="#3b2a1f"/><path d="M28 43 q4 3 8 0" stroke="#3b2a1f" stroke-width="1.9" fill="none" stroke-linecap="round"/></svg>', "꽉 잡아요"),
    ('<svg width="60" height="60" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><circle cx="30" cy="32" r="18" fill="#f0e2d2" stroke="#8b5e3c" stroke-width="2"/><path d="M20 28 q4.5 -3.5 9 0" stroke="#3b2a1f" stroke-width="2.2" fill="none" stroke-linecap="round"/><path d="M33 28 q4.5 -3.5 9 0" stroke="#3b2a1f" stroke-width="2.2" fill="none" stroke-linecap="round"/><path d="M24 40 q6 4.5 12 0" stroke="#8b5e3c" stroke-width="2.2" fill="none" stroke-linecap="round"/><path d="M47 24 q3.5 4.5 0 9 q-3.5 -4.5 0 -9 Z" fill="#7a8f63"/></svg>', "퇴근하고파"),
    ('<svg width="60" height="60" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><path d="M22 15 q2 4 0 7 M30 14 q2 4 0 7" stroke="#c98a3a" stroke-width="2" fill="none" stroke-linecap="round"/><rect x="16" y="25" width="26" height="24" rx="5" fill="#fffaf4" stroke="#8b5e3c" stroke-width="2"/><path d="M42 29 h5 a6 6 0 0 1 0 12 h-5" fill="none" stroke="#8b5e3c" stroke-width="2"/><rect x="18" y="26" width="22" height="6" rx="2" fill="#8b5e3c"/><circle cx="26" cy="40" r="1.7" fill="#3b2a1f"/><circle cx="33" cy="40" r="1.7" fill="#3b2a1f"/><path d="M27 44 q3 2 6 0" stroke="#3b2a1f" stroke-width="1.6" fill="none" stroke-linecap="round"/></svg>', "졸려요"),
]

_SESSION_DEFAULTS = {
    "active_tab": "홈",
    "saved_routes": [],
    "selected_route": None,
    "logged_in": False,
    "user_email": "",
    "notify_on": False,
    "congestion_display": "퍼센트",
    "seat_display": "퍼센트",
    "crowd_reports": [],
    "ui_transport": "지하철",
    "ui_dep_subway": "강남역",
    "ui_arr_subway": "사당역",
    "ui_dep_bus": "강남역10번출구",
    "ui_arr_bus": "사당역4번출구",
    "ui_bus_no": "146번",
    "ui_time": time(18, 30),
    "rep_transport": "지하철",
}
for _k, _v in _SESSION_DEFAULTS.items():
    st.session_state.setdefault(_k, _v)
for _key, _fb in (("ui_dep_subway", "강남역"), ("ui_arr_subway", "사당역")):
    if st.session_state[_key] not in station_options:
        st.session_state[_key] = station_options[_default_index(station_options, _fb)]


# --------------------------- 공통 유틸/로직 ---------------------------
def _go(tab):
    st.session_state.active_tab = tab
    st.rerun()


def _select_route(transport, dep, arr, dep_time, bus_no=""):
    st.session_state.selected_route = {
        "transport": transport, "dep": dep, "arr": arr, "dep_time": dep_time, "bus_no": bus_no,
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


def _compute_prediction(route):
    transport = route["transport"]; dep = route["dep"]; arr = route["arr"]
    dep_time = route["dep_time"]; bus_no = route.get("bus_no", "")
    real = None
    if transport == "지하철":
        real = seoul_api.get_real_congestion_series(
            CONGESTION_AUTH_KEY, dep, dep_time.hour, dep_time.minute, list(range(0, 65, 5)))
    real_pct = tuple(real["congestion_pct"]) if real else None
    real_line = real["line"] if real else None
    df, wait_spot, is_real, data_line = build_prediction(
        MOBILE_PRESET, transport, dep, arr, dep_time.hour, dep_time.minute, real_pct, real_line)
    cc = float(df.iloc[0]["congestion_pct"]); cs = float(df.iloc[0]["seat_prob_pct"])
    level_label, level_color = congestion_level_color(cc)
    seat_status, seat_color = _seat_tier(cs)
    fut = df[(df["minutes_offset"] > 0) & (df["minutes_offset"] <= 30)]
    best = fut.loc[fut["seat_prob_pct"].idxmax()]
    return {
        "transport": transport, "dep": dep, "arr": arr, "dep_time": dep_time, "bus_no": bus_no,
        "df": df, "wait_spot": wait_spot, "is_real": is_real, "data_line": data_line,
        "current_congestion": cc, "current_seat_prob": cs,
        "level_label": level_label, "level_color": level_color,
        "seat_status": seat_status, "seat_color": seat_color,
        "best_offset": int(best["minutes_offset"]), "best_prob": float(best["seat_prob_pct"]),
        "best_time_label": str(best["time_label"]),
    }


def _crowd_levels_for(transport):
    return SUBWAY_CROWD_LEVELS if transport == "지하철" else BUS_CROWD_LEVELS


def _route_key(transport, a, b, c):
    return f"{transport}|{a}|{b}|{c}"


def _signal_key(transport, line, station):
    return f"지하철|{station}" if transport == "지하철" else f"버스|{line}|{station}"


def _guess_band(dep_time):
    h = dep_time.hour
    if 7 <= h < 9:
        return CROWD_TIME_BANDS[0]
    if 9 <= h < 12:
        return CROWD_TIME_BANDS[1]
    if 12 <= h < 14:
        return CROWD_TIME_BANDS[2]
    if 14 <= h < 17:
        return CROWD_TIME_BANDS[3]
    if 17 <= h < 20:
        return CROWD_TIME_BANDS[4]
    return CROWD_TIME_BANDS[5]


def _points_total():
    return len(st.session_state.crowd_reports) * REPORT_POINTS


def _points_today():
    today = datetime.now().date()
    return sum(REPORT_POINTS for r in st.session_state.crowd_reports if r["ts"].date() == today)


def _fresh_reports(signal_key=None):
    now = datetime.now(); out = []
    for r in st.session_state.crowd_reports:
        if now - r["ts"] <= timedelta(minutes=FRESH_MINUTES) and (signal_key is None or r["signal_key"] == signal_key):
            out.append(r)
    return out


def _recent_duplicate(route_key):
    now = datetime.now()
    for r in st.session_state.crowd_reports:
        if r["route_key"] == route_key and now - r["ts"] < timedelta(minutes=DEDUP_MINUTES):
            return r
    return None


def _minutes_ago(ts):
    m = int((datetime.now() - ts).total_seconds() // 60)
    return "방금 전" if m <= 0 else f"{m}분 전"


# --------------------------- 공통 렌더 ---------------------------
def _status_bar():
    st.markdown(
        f'<div class="status-bar"><span>{datetime.now().strftime("%H:%M")}</span>'
        f'<span class="dots">● ● ●</span></div>',
        unsafe_allow_html=True,
    )


def _render_app_brand():
    """전 탭 공통 헤더 — 큰 자리각 + 랜덤 스티커(컴팩트)."""
    idx = st.session_state.setdefault("home_sticker", random.randrange(len(STICKERS)))
    svg, cap = STICKERS[idx % len(STICKERS)]
    st.markdown(
        f'<div class="brand-hero"><div style="flex:1; min-width:0;">'
        f'<div class="big-name">자리각</div>'
        f'<div class="big-tag">지금 타면 앉을 각인지 확인해요</div></div>'
        f'<div class="sticker">{svg}<div class="sticker-cap">{escape(cap)}</div></div></div>',
        unsafe_allow_html=True,
    )


def _mode_line():
    st.markdown(
        f'<div class="data-note">데모 상태 · <b style="color:{DATA_MODE_COLOR};">{DATA_MODE_TEXT}</b></div>',
        unsafe_allow_html=True,
    )


def _crowd_signal_note(transport, signal_key, levels):
    fresh = _fresh_reports(signal_key)
    if not fresh:
        matched = [r for r in st.session_state.crowd_reports if r["signal_key"] == signal_key]
        tail = f"최근 {FRESH_MINUTES}분 내 제보 없음(오래된 제보 {len(matched)}건)" if matched else "아직 제보 없음"
        st.markdown(
            f'<div class="data-note">사용자 제보 기반 혼잡도 · {tail}<br/>'
            f'<b style="color:var(--warning);">비공식 · 사용자 제보</b> (공식 실시간 아님)</div>',
            unsafe_allow_html=True,
        )
        return
    idxs = [r["level_idx"] for r in fresh]
    rep = levels[round(sum(idxs) / len(idxs))]
    latest = max(fresh, key=lambda r: r["ts"])
    st.markdown(
        f'<div class="data-note">사용자 제보 기반 혼잡도 · '
        f'<b style="color:var(--primary);">{escape(rep)}</b> '
        f'(최근 {FRESH_MINUTES}분 {len(fresh)}건, 최근 “{escape(latest["level"])}” {_minutes_ago(latest["ts"])})<br/>'
        f'<b style="color:var(--warning);">비공식 · 사용자 제보</b> (공식 실시간 아님)</div>',
        unsafe_allow_html=True,
    )


def _saved_routes_list():
    saved = st.session_state.saved_routes
    if not saved:
        st.markdown(
            '<div class="empty-state"><div class="empty-title">저장한 경로 없음</div>'
            '<div class="empty-desc">예측 화면에서 “경로 저장”을 눌러보세요.</div></div>',
            unsafe_allow_html=True,
        )
        return
    for r in saved[-5:][::-1]:
        title = r.get("label") or f'{r["dep"]} → {r["arr"]}'
        st.markdown(
            f'<div class="saved-row"><div class="saved-title">{escape(title)}</div>'
            f'<div class="saved-meta">{escape(r["transport"])} · {escape(r["time"])} · 예상 좌석 {r["prob"]:.0f}%</div></div>',
            unsafe_allow_html=True,
        )


# --------------------------- 탭: 홈 ---------------------------
def _render_home():
    _status_bar(); _render_app_brand()
    _mode_line()
    st.markdown('<div class="data-note">퇴근길 지하철·버스가 얼마나 붐빌지, 지금 타면 앉을 수 있을지 예상해 드려요.</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">빠른 시작</div>', unsafe_allow_html=True)
    if st.button("지하철로 시작", use_container_width=True, type="primary", key="qs_subway"):
        st.session_state.ui_transport = "지하철"; _go("경로")
    if st.button("버스로 시작", use_container_width=True, key="qs_bus"):
        st.session_state.ui_transport = "버스"; _go("경로")

    with st.expander("정보 구분 안내"):
        st.markdown(
            "- 공식 실시간 도착정보 — 열차·버스가 몇 분 뒤 오는지(사실)\n"
            "- 사용자 제보 기반 혼잡도 — 이용자가 남긴 붐빔(비공식)\n"
            "- 예상 좌석 확률 — 혼잡도로 추정한 값(실측 아님)\n"
            "- 참고용 통계 — 과거 승하차 등 집계"
        )


# --------------------------- 탭: 경로 ---------------------------
def _render_route():
    _status_bar(); _render_app_brand()

    st.markdown('<div class="section-title">경로 선택</div>', unsafe_allow_html=True)
    transport = st.radio("교통수단", ["지하철", "버스"], horizontal=True, label_visibility="collapsed", key="ui_transport")
    if transport == "지하철":
        dep = st.selectbox("출발역", station_options, key="ui_dep_subway")
        arr = st.selectbox("도착역", station_options, key="ui_arr_subway")
        bus_no = ""
        ll = _line_label(dep)
        if ll:
            st.markdown(f'<div class="data-note">대표 호선 · <b style="color:var(--primary);">{escape(ll)}</b></div>', unsafe_allow_html=True)
    else:
        dep = st.text_input("출발 정류장", key="ui_dep_bus")
        arr = st.text_input("도착 정류장", key="ui_arr_bus")
        bus_no = st.selectbox("버스 번호", BUS_NUMBER_OPTIONS, key="ui_bus_no")
        if bus_no == "직접 입력":
            bus_no = st.text_input("버스 번호 직접 입력", value="146번", key="ui_bus_no_custom")
    dep_time = st.time_input("출발 시간", key="ui_time")
    if st.button("예측 보기", use_container_width=True, type="primary", key="route_go"):
        _select_route(transport, dep, arr, dep_time, bus_no)

    with st.expander("추천 경로"):
        for i, r in enumerate(DEMO_ROUTES):
            head, sub, _ = _route_headline(r["transport"], r["dep"], r["arr"], r["bus_no"], False, None)
            st.markdown(
                f'<div class="route-meta" style="margin:2px 0 4px;">{head} · {escape(sub)} · {r["time"].strftime("%H:%M")}</div>',
                unsafe_allow_html=True,
            )
            if st.button("예측 보기", key=f"demo_go_{i}", use_container_width=True):
                _select_route(r["transport"], r["dep"], r["arr"], r["time"], r["bus_no"])


# --------------------------- 탭: 예측 (제보 통합) ---------------------------
def _render_predict():
    _status_bar(); _render_app_brand()
    route = st.session_state.selected_route
    if not route:
        st.markdown(
            '<div class="empty-state"><div class="empty-title">선택된 경로가 없어요</div>'
            '<div class="empty-desc">경로 탭에서 먼저 경로를 선택해 주세요.</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("경로 선택하러 가기", use_container_width=True, type="primary", key="predict_goroute"):
            _go("경로")
        return

    _render_prediction_result(route)
    _render_report_section()


def _render_prediction_result(route):
    p = _compute_prediction(route)
    head, sub, saved_label = _route_headline(
        p["transport"], p["dep"], p["arr"], p["bus_no"], p["is_real"], p["data_line"])
    source_text = f"실데이터 · {p['data_line']}" if p["is_real"] else "데모 · 예상치"
    source_color = "var(--accent)" if p["is_real"] else "var(--warning)"

    st.markdown('<div class="section-title">예상 결과</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="route-strip"><div class="route-main"><span>{head}</span></div>'
        f'<div class="route-meta">{escape(sub)} · {p["dep_time"].strftime("%H:%M")} · '
        f'<span style="color:{source_color};">{escape(source_text)}</span></div></div>',
        unsafe_allow_html=True,
    )

    seat_main = f'{p["current_seat_prob"]:.0f}%' if st.session_state.seat_display == "퍼센트" else escape(p["seat_status"])
    advice = (
        f'{p["best_offset"]}분 뒤 {p["best_time_label"]}에 타면 더 유리'
        if p["best_prob"] - p["current_seat_prob"] >= 5 else "지금 타도 좋아요"
    )
    st.markdown(
        f'<div class="result-hero"><div class="label">예상 좌석 확률</div>'
        f'<div class="value" style="color:{p["seat_color"]};">{seat_main}</div>'
        f'<div class="copy">{escape(p["seat_status"])} · {advice}</div></div>',
        unsafe_allow_html=True,
    )

    cong_main = f'{p["current_congestion"]:.0f}%' if st.session_state.congestion_display == "퍼센트" else escape(p["level_label"])
    st.markdown(
        f'<div class="metric-grid">'
        f'<div class="metric-card"><div class="metric-label">예상 혼잡도</div>'
        f'<div class="metric-value" style="color:{p["level_color"]};">{cong_main}</div>'
        f'<div class="metric-note">{escape(p["level_label"])}</div></div>'
        f'<div class="metric-card"><div class="metric-label">추천 대기 위치</div>'
        f'<div class="metric-value" style="color:var(--accent);">{escape(p["wait_spot"])}</div>'
        f'<div class="metric-note">{p["best_offset"]}분 뒤</div></div></div>',
        unsafe_allow_html=True,
    )

    sig = _signal_key(
        p["transport"],
        (_line_label(p["dep"]) or "") if p["transport"] == "지하철" else p["bus_no"],
        p["dep"],
    )
    _crowd_signal_note(p["transport"], sig, _crowd_levels_for(p["transport"]))

    with st.expander("시간대별 그래프 · 실시간 도착정보"):
        st.markdown(
            '<div class="data-note">공식 실시간 도착정보는 데모에서 미연동입니다(백엔드 /realtime 예정). '
            '아래 그래프는 예상치입니다.</div>',
            unsafe_allow_html=True,
        )
        df = p["df"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["minutes_offset"], y=df["seat_prob_pct"], mode="lines+markers",
            name="좌석 확률", line=dict(color="#7a8f63", width=3), marker=dict(size=6),
            fill="tozeroy", fillcolor="rgba(122, 143, 99, 0.14)"))
        fig.add_trace(go.Scatter(
            x=df["minutes_offset"], y=df["congestion_pct"], mode="lines",
            name="혼잡도", line=dict(color="#b85c38", width=2, dash="dot")))
        fig.add_vline(x=p["best_offset"], line_dash="dot", line_color="#5f3d28")
        fig.update_layout(
            template="plotly_white", height=230, margin=dict(l=6, r=6, t=16, b=8),
            paper_bgcolor="#f6efe7", plot_bgcolor="#f6efe7", font=dict(color="#3b2a1f"),
            legend=dict(orientation="h", y=1.15, x=0, font=dict(size=11)),
            xaxis=dict(title=None, tickmode="array", tickvals=df["minutes_offset"][::2],
                       ticktext=df["time_label"][::2], gridcolor="#e1d2c1"),
            yaxis=dict(title=None, range=[0, 105], gridcolor="#e1d2c1"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    c1, c2 = st.columns(2)
    with c1:
        if st.button("경로 저장", use_container_width=True, key="save_route"):
            st.session_state.saved_routes.append({
                "transport": p["transport"], "dep": p["dep"], "arr": p["arr"],
                "label": saved_label, "time": p["dep_time"].strftime("%H:%M"),
                "prob": p["current_seat_prob"],
            })
            st.toast("저장되었습니다")
    with c2:
        if st.button("다른 경로 선택", use_container_width=True, key="predict_change"):
            _go("경로")


def _render_report_section():
    st.markdown('<div class="section-title">혼잡도 제보하기</div>', unsafe_allow_html=True)
    if not st.session_state.logged_in:
        st.markdown(
            '<div class="data-note">로그인하면 혼잡도를 제보하고 포인트를 받을 수 있어요. (MY 탭에서 로그인)</div>',
            unsafe_allow_html=True,
        )
        if st.button("로그인하러 가기", use_container_width=True, key="rep_login_go"):
            _go("MY")
        return

    st.markdown(
        '<div class="data-note">제보 1회당 +10P · 같은 경로는 5분 뒤 다시 제보 가능 · '
        '<b style="color:var(--warning);">비공식 · 사용자 제보</b></div>',
        unsafe_allow_html=True,
    )
    transport = st.radio("교통수단", ["지하철", "버스"], horizontal=True, label_visibility="collapsed", key="rep_transport")
    levels = _crowd_levels_for(transport)
    if transport == "지하철":
        line = st.text_input("호선", value="2호선")
        station = st.text_input("역", value="강남역")
        direction = st.selectbox("방향", SUBWAY_DIRECTIONS)
        car = st.selectbox("차량 칸 번호", [str(i) for i in range(1, 11)])
        route_key = _route_key("지하철", line, station, direction)
        extra = f"{direction} · {car}칸"
    else:
        line = st.text_input("버스 번호", value="146번")
        station = st.text_input("정류장", value="강남역10번출구")
        band = st.selectbox("시간대", CROWD_TIME_BANDS, index=_default_index(CROWD_TIME_BANDS, _guess_band(st.session_state.get("ui_time", time(18, 30)))))
        route_key = _route_key("버스", line, station, band)
        extra = band
    level = st.radio("혼잡도 단계", levels)
    signal_key = _signal_key(transport, line, station)

    if st.button("제보하고 +10P", use_container_width=True, type="primary", key="rep_submit"):
        dup = _recent_duplicate(route_key)
        if dup:
            st.warning(f"같은 경로는 {DEDUP_MINUTES}분 후 다시 제보할 수 있어요. (직전 {_minutes_ago(dup['ts'])})")
        else:
            st.session_state.crowd_reports.append({
                "ts": datetime.now(), "transport": transport, "user": st.session_state.user_email,
                "line": line, "station": station, "level": level, "level_idx": levels.index(level),
                "route_key": route_key, "signal_key": signal_key, "extra": extra,
            })
            st.toast(f"제보 완료! +{REPORT_POINTS}P")
            st.rerun()

    _crowd_signal_note(transport, signal_key, levels)


# --------------------------- 탭: MY ---------------------------
def _render_my():
    _status_bar(); _render_app_brand()

    if not st.session_state.logged_in:
        st.markdown('<div class="section-title">로그인</div>', unsafe_allow_html=True)
        email = st.text_input("이메일", placeholder="you@example.com")
        if st.button("로그인", use_container_width=True, type="primary", key="login_btn"):
            st.session_state.logged_in = True
            st.session_state.user_email = email.strip() or "guest@demo.com"
            st.rerun()
        st.markdown(
            '<div class="data-note">발표용 목업 로그인입니다. 실제 인증·개인정보 저장은 없습니다.</div>',
            unsafe_allow_html=True,
        )
        return

    saved = st.session_state.saved_routes
    fav = "-"
    if saved:
        counts = {}
        for r in saved:
            counts[r["transport"]] = counts.get(r["transport"], 0) + 1
        fav = max(counts, key=counts.get)

    st.markdown('<div class="section-title">내 계정</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="data-note">{escape(st.session_state.user_email)} · '
        f'저장 경로 {len(saved)}개 · 자주 타는 {escape(fav)}</div>',
        unsafe_allow_html=True,
    )

    total = _points_total(); today = _points_today()
    st.markdown(
        f'<div class="metric-grid">'
        f'<div class="metric-card"><div class="metric-label">오늘 획득</div>'
        f'<div class="metric-value" style="color:var(--accent);">+{today}P</div>'
        f'<div class="metric-note">오늘 제보 포인트</div></div>'
        f'<div class="metric-card"><div class="metric-label">누적 포인트</div>'
        f'<div class="metric-value" style="color:var(--primary);">{total}P</div>'
        f'<div class="metric-note">지금까지 모은 포인트</div></div></div>',
        unsafe_allow_html=True,
    )

    with st.expander("제보 기록"):
        reports = st.session_state.crowd_reports
        if not reports:
            st.markdown('<div class="data-note">아직 제보가 없어요. 예측 탭에서 남겨보세요.</div>', unsafe_allow_html=True)
        else:
            for r in reports[-6:][::-1]:
                stale = datetime.now() - r["ts"] > timedelta(minutes=FRESH_MINUTES)
                tag = " · 오래된 제보" if stale else ""
                st.markdown(
                    f'<div class="saved-row"><div class="saved-title">{escape(r["transport"])} · {escape(r["line"])} {escape(r["station"])}</div>'
                    f'<div class="saved-meta">{escape(r["level"])} · {escape(r.get("extra", ""))} · {_minutes_ago(r["ts"])}{tag} · +{REPORT_POINTS}P</div></div>',
                    unsafe_allow_html=True,
                )

    with st.expander("리워드 (데모)"):
        for need, name in REWARDS:
            unlocked = total >= need
            color = "var(--accent)" if unlocked else "var(--muted)"
            status = "교환 가능" if unlocked else f"{need - total}P 남음"
            st.markdown(
                f'<div class="route-meta" style="margin:2px 0 6px; color:{color};">{escape(name)} · {need}P · {status}</div>',
                unsafe_allow_html=True,
            )
        st.markdown('<div class="data-note">리워드는 실제 지급이 아니라 발표용 데모입니다.</div>', unsafe_allow_html=True)

    with st.expander("저장한 경로"):
        _saved_routes_list()

    with st.expander("설정"):
        _mode_line()
        st.toggle("알림 받기", key="notify_on")
        st.radio("혼잡도 표시", ["퍼센트", "등급"], horizontal=True, key="congestion_display")
        st.radio("좌석 확률 표시", ["퍼센트", "상태"], horizontal=True, key="seat_display")
        st.caption("데이터 출처: subwConfusion · CardSubwayStatsNew · CardBusStatisticsServiceNew · realtimeStationArrival. 좌석 확률은 예상치입니다.")
        if st.button("저장 경로 초기화", use_container_width=True, key="reset_saved"):
            st.session_state.saved_routes = []
            st.toast("초기화되었습니다")
            st.rerun()
        if st.button("로그아웃", use_container_width=True, key="logout_btn"):
            st.session_state.logged_in = False
            st.rerun()


# --------------------------- 하단 하트 탭 (클릭 가능) ---------------------------
def _render_bottom_nav():
    st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)
    cols = st.columns(len(TABS))
    for col, name in zip(cols, TABS):
        with col:
            active = st.session_state.active_tab == name
            if st.button(name, key=f"nav_{TAB_SLUGS[name]}", use_container_width=True,
                         type="primary" if active else "secondary"):
                if not active:
                    st.session_state.active_tab = name
                    st.rerun()


_RENDER = {"홈": _render_home, "경로": _render_route, "예측": _render_predict, "MY": _render_my}
_RENDER.get(st.session_state.active_tab, _render_home)()
st.markdown('<div class="app-spacer"></div>', unsafe_allow_html=True)
_render_bottom_nav()
