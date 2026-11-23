import os
import json
import time
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import html
import hmac
from notifier import build_html_email, DISCLAIMER

IST = timezone(timedelta(hours=5, minutes=30))
SNAPSHOT_PATH = "data/market_snapshot.json"
DEFAULT_STALE_HOURS = 6

st.set_page_config(
    page_title="AURA BI AGENT | Market Intelligence Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');

    @keyframes pulseGold {
        0% { box-shadow: 0 0 0 0 rgba(212, 175, 55, 0.25); }
        70% { box-shadow: 0 0 0 8px rgba(212, 175, 55, 0); }
        100% { box-shadow: 0 0 0 0 rgba(212, 175, 55, 0); }
    }

    .stApp {
        background: radial-gradient(circle at 15% 0%, #111C33 0%, #070B14 55%, #05080F 100%);
        color: #E2E8F0;
        font-family: 'Inter', sans-serif;
    }
    header[data-testid="stHeader"] {
        background: rgba(7, 11, 20, 0.85) !important;
        backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }
    section[data-testid="stSidebar"] {
        background: #090E1A !important;
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }
    .block-container { padding-top: 1.3rem; padding-bottom: 1.5rem; max-width: 1640px; }

    div[data-testid="stExpander"] p,
    div[data-testid="stExpander"] li,
    div[data-testid="stExpander"] code {
        white-space: normal !important;
        word-break: break-word !important;
        overflow-wrap: anywhere !important;
    }

    .brand-title {
        font-size: 25px; font-weight: 700; letter-spacing: 1.1px;
        background: linear-gradient(90deg, #F8FAFC 0%, #E2C06D 60%, #D4AF37 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin: 0; line-height: 1.2;
    }
    .brand-sub { font-size: 12px; color: #94A3B8; letter-spacing: 0.3px; margin-top: 3px; }
    .regime-pill {
        display: inline-block; padding: 2px 9px; border-radius: 999px;
        background: rgba(212, 175, 55, 0.14); border: 1px solid rgba(212, 175, 55, 0.4);
        color: #F3D58D; font-size: 10.5px; font-weight: 600; margin-left: 8px;
        animation: pulseGold 2.8s infinite;
    }
    .status-fresh {
        display: inline-block; padding: 2px 9px; border-radius: 999px;
        background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(52, 211, 153, 0.45);
        color: #34D399; font-size: 10.5px; font-weight: 700; margin-left: 6px;
    }
    .status-aging {
        display: inline-block; padding: 2px 9px; border-radius: 999px;
        background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(251, 191, 36, 0.45);
        color: #FBBF24; font-size: 10.5px; font-weight: 700; margin-left: 6px;
    }
    .status-stale {
        display: inline-block; padding: 2px 9px; border-radius: 999px;
        background: rgba(239, 68, 68, 0.18); border: 1px solid rgba(248, 113, 113, 0.5);
        color: #F87171; font-size: 10.5px; font-weight: 700; margin-left: 6px;
    }
    .tbl-header-row {
        display: flex; align-items: baseline; justify-content: space-between;
        margin-top: 0.65rem; margin-bottom: 0.35rem; gap: 10px; flex-wrap: wrap;
    }
    .tbl-title {
        color: #E2C06D; font-weight: 600; font-size: 15.5px; letter-spacing: 0.25px;
    }
    .tbl-asof {
        font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #94A3B8;
        background: rgba(30, 41, 59, 0.65); border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 2px 8px; border-radius: 5px;
    }

    .kpi-card {
        background: rgba(17, 25, 40, 0.72);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-top: 2px solid rgba(212, 175, 55, 0.7);
        border-radius: 9px; padding: 10px 12px;
        transition: transform 0.16s ease, border-color 0.16s ease;
    }
    .kpi-card:hover { transform: translateY(-2px); border-color: rgba(212, 175, 55, 0.6); }
    .kpi-label { font-size: 9.5px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }
    .kpi-val { font-size: 16.5px; font-weight: 700; color: #F8FAFC; font-family: 'JetBrains Mono', monospace; margin-top: 3px; }
    .kpi-pos { font-size: 11px; color: #34D399; font-weight: 700; margin-top: 2px; font-family: 'JetBrains Mono', monospace; }
    .kpi-neg { font-size: 11px; color: #F87171; font-weight: 700; margin-top: 2px; font-family: 'JetBrains Mono', monospace; }

    .ai-box {
        background: rgba(17, 25, 40, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-left: 3px solid #D4AF37;
        padding: 12px 16px; border-radius: 8px; margin-bottom: 8px;
        color: #E2E8F0; font-size: 13px; line-height: 1.5;
    }
    .alert-card {
        background: rgba(17, 25, 40, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px; padding: 10px 14px; margin-bottom: 8px;
    }
    .news-card {
        background: rgba(17, 25, 40, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 8px; padding: 11px 15px; margin-bottom: 8px;
    }
    .badge {
        display: inline-block; padding: 2px 7px; border-radius: 4px;
        font-size: 10px; font-weight: 700; background: rgba(212, 175, 55, 0.14);
        color: #E2C06D; margin-right: 6px;
    }
    h3, h4 { color: #E2C06D !important; font-weight: 600 !important; letter-spacing: 0.25px; margin-top: 0.5rem !important; margin-bottom: 0.35rem !important; }
    button[data-baseweb="tab"] {
        color: #94A3B8 !important; font-weight: 600 !important; font-size: 13px !important; padding: 8px 11px !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #F3D58D !important; border-bottom-color: #D4AF37 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


STANCE_LABELS = {"Buy": "Favourable", "Hold": "Neutral", "Sell": "Cautious"}


def esc(x):
    return html.escape(str(x if x is not None else ""))


def safe_link(u):
    u = str(u or "")
    return u if u.startswith(("http://", "https://")) else "#"


def parse_snapshot_dt(snap):
    if not snap:
        return None
    raw_str = snap.get("updated_at_ist", "")
    for fmt in ("%d %b %Y, %I:%M %p IST", "%d %b %Y, %H:%M IST"):
        try:
            dt = datetime.strptime(raw_str, fmt)
            return dt.replace(tzinfo=IST)
        except ValueError:
            continue
    if os.path.exists(SNAPSHOT_PATH):
        mtime = os.path.getmtime(SNAPSHOT_PATH)
        return datetime.fromtimestamp(mtime, tz=IST)
    return None


def format_as_of_stamp(snap):
    dt = parse_snapshot_dt(snap)
    if dt:
        return f"as of {dt.strftime('%d %b')} (at {dt.strftime('%H:%M')})"
    return "as of —"


def render_section_heading(title, as_of_text):
    st.markdown(
        f"""
        <div class="tbl-header-row">
            <span class="tbl-title">{esc(title)}</span>
            <span class="tbl-asof">{esc(as_of_text)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


RUN_TIMES = [(8, 30), (16, 30)]  # scheduled refresh slots, IST, Mon-Fri


def last_scheduled_run(now):
    for back in range(0, 6):
        day = (now - timedelta(days=back)).date()
        if day.weekday() >= 5:
            continue
        for hh, mm in sorted(RUN_TIMES, reverse=True):
            t = datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST)
            if t <= now:
                return t
    return None


def get_freshness_info(snap, stale_hours=DEFAULT_STALE_HOURS):
    """Freshness is judged against the last SCHEDULED run, so weekends do not read as stale."""
    now_ist = datetime.now(IST)
    dt = parse_snapshot_dt(snap)
    if not dt:
        return "UNKNOWN", "No timestamp available", "status-stale"

    age_delta = now_ist - dt
    age_hours = max(0.0, age_delta.total_seconds() / 3600.0)
    if age_hours < 1:
        age_label = f"{max(1, int(age_delta.total_seconds() // 60))}m ago"
    elif age_hours < 24:
        age_label = f"{age_hours:.1f}h ago"
    else:
        age_label = f"{age_delta.days}d {(age_delta.seconds // 3600)}h ago"

    last_run = last_scheduled_run(now_ist)
    lag_h = ((last_run - dt).total_seconds() / 3600.0) if last_run else 0.0
    run_txt = f"; last scheduled run {last_run.strftime('%a %H:%M')} IST" if last_run else ""
    if lag_h <= 0.5:
        return "UP TO DATE", f"Fetched {age_label}{run_txt}", "status-fresh"
    if lag_h <= 6:
        return "AGING DATA", f"Fetched {age_label}{run_txt}", "status-aging"
    return "STALE / NOT NEWLY UPDATED", f"Fetched {age_label}{run_txt} \u2014 showing prior snapshot", "status-stale"


def execute_data_refresh(prev_snap=None):
    prev_updated = (prev_snap or {}).get("updated_at_ist")
    prev_nifty = None
    for x in (prev_snap or {}).get("markets", {}).get("indian_equity", []):
        if "nifty 50" in x.get("name", "").lower():
            prev_nifty = x.get("price")
            break

    try:
        from fetch_data import run_fetch
        from ai_analyst import run_ai_analysis
        run_fetch()
        if os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None):
            if "GEMINI_API_KEY" not in os.environ and "GEMINI_API_KEY" in st.secrets:
                os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
        run_ai_analysis()

        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            final_snap = json.load(f)

        new_nifty = None
        for x in final_snap.get("markets", {}).get("indian_equity", []):
            if "nifty 50" in x.get("name", "").lower():
                new_nifty = x.get("price")
                break

        has_any_data = any(bool(v) for v in final_snap.get("markets", {}).values())
        unchanged_prices = (prev_nifty is not None and new_nifty == prev_nifty and prev_updated == final_snap.get("updated_at_ist"))

        if not has_any_data:
            st.session_state["fetch_notice"] = ("warning", "Auto-fetch ran, but market feeds returned empty; displaying existing snapshot if available.")
        elif unchanged_prices:
            st.session_state["fetch_notice"] = ("info", f"Fetch completed at {final_snap.get('updated_at_ist')}; underlying prices match the previous fetch.")
        else:
            st.session_state["fetch_notice"] = ("success", f"New data fetched at {final_snap.get('updated_at_ist')}.")
        return final_snap
    except Exception as e:
        st.session_state["fetch_notice"] = ("error", f"Auto-fetch failed ({e}). Showing last saved data.")
        return prev_snap


@st.cache_data(show_spinner=False)
def _read_snapshot(path, mtime):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_snapshot():
    if os.path.exists(SNAPSHOT_PATH):
        return _read_snapshot(SNAPSHOT_PATH, os.path.getmtime(SNAPSHOT_PATH))
    return None


if "auto_fetch_enabled" not in st.session_state:
    st.session_state["auto_fetch_enabled"] = True
if "stale_threshold_hours" not in st.session_state:
    st.session_state["stale_threshold_hours"] = DEFAULT_STALE_HOURS
if "last_auto_check_ts" not in st.session_state:
    st.session_state["last_auto_check_ts"] = 0.0

snapshot = load_snapshot()

try:
    ADMIN_PW = st.secrets.get("ADMIN_PASSWORD")
except Exception:
    ADMIN_PW = None

with st.sidebar:
    st.markdown("### \u26a1 AURA BI AGENT")
    st.caption("Market & Valuation Intelligence Terminal")
    st.divider()
    st.caption("Data refreshes automatically at 8:30 AM & 4:30 PM IST (Mon\u2013Fri) via a scheduled job. This page only reads the latest snapshot.")

    if ADMIN_PW:
        pw = st.text_input("Admin password", type="password")
        if pw and hmac.compare_digest(pw, str(ADMIN_PW)):
            if st.button("\U0001f504 Refresh now (admin)", width="stretch", type="primary"):
                with st.spinner("Fetching prices, flows, AMFI NAVs & AI brief..."):
                    snapshot = execute_data_refresh(snapshot)
                st.cache_data.clear()
                st.rerun()

    if snapshot:
        printable_html = build_html_email(snapshot, "https://share.streamlit.io")
        st.download_button(
            label="\U0001f4c4 Export Printable Brief",
            data=printable_html,
            file_name="AURA_BI_Daily_Brief.html",
            mime="text/html",
            width="stretch",
        )
        st.caption("Open the file in a browser and press Ctrl+P to save as PDF.")

if not snapshot:
    st.warning("No snapshot yet. Run the scheduled job (GitHub Actions \u2192 Refresh market data \u2192 Run workflow) or run `python fetch_data.py` locally.")
    st.stop()

ai = snapshot.get("ai_strategist", {})
macro = snapshot.get("macro_manual", {})
markets = snapshot.get("markets", {})
flows = snapshot.get("institutional_flows", {})
fund_alpha = snapshot.get("fund_alpha", [])
amfi_debt_schemes = snapshot.get("amfi_debt_schemes", [])
amfi_monthly = snapshot.get("amfi_monthly_manual", {})
nfo_watchlist = snapshot.get("nfo_watchlist", [])
whats_interesting = snapshot.get("whats_interesting", [])
last_fetched_str = snapshot.get("updated_at_ist", "Unknown")
as_of_stamp = format_as_of_stamp(snapshot)
fresh_tag, fresh_detail, fresh_css = get_freshness_info(snapshot, st.session_state["stale_threshold_hours"])


def format_price(item):
    if not item or item.get("price") is None:
        return "—"
    cur = item.get("currency", "")
    val = item["price"]
    if cur == "%":
        return f"{val:.2f}%"
    if cur in ["₹", "$"]:
        return f"{cur}{val:,.2f}"
    return f"{val:,.2f}"


def split_stance(stance_raw):
    text = stance_raw or "Hold | mixed signals"
    if " | " in text:
        head, reason = text.split(" | ", 1)
    else:
        head, reason = text, ""
    h = head.strip().lower()
    if h.startswith("buy"):
        bucket = "Buy"
    elif h.startswith("sell"):
        bucket = "Sell"
    else:
        bucket = "Hold"
    return bucket, STANCE_LABELS.get(bucket, head.strip()), reason.strip()


def format_stance_cell(stance_raw):
    bucket, head, reason = split_stance(stance_raw)
    if bucket == "Buy":
        tag_bg, tag_fg = "rgba(16, 185, 129, 0.18)", "#34D399"
    elif bucket == "Sell":
        tag_bg, tag_fg = "rgba(239, 68, 68, 0.18)", "#F87171"
    else:
        tag_bg, tag_fg = "rgba(245, 158, 11, 0.18)", "#FBBF24"

    reason_html = (
        f"<div style='font-size:11px;color:#E2E8F0;line-height:1.25;margin-top:2px;white-space:normal;'>{esc(reason)}</div>"
        if reason else ""
    )
    return (
        f"<div style='min-width:210px;max-width:260px;white-space:normal;'>"
        f"<span style='display:inline-block;padding:1px 6px;border-radius:4px;background:{tag_bg};color:{tag_fg};font-size:10.5px;font-weight:700;'>{esc(head)}</span>"
        f"{reason_html}</div>"
    )


def pct_badge_html(v):
    if v is None or pd.isna(v):
        return "<span style='color:#64748B;'>—</span>"
    sign = "+" if v > 0 else ""
    if v >= 0:
        bg = "rgba(16, 185, 129, 0.24)" if v >= 10 else "rgba(16, 185, 129, 0.11)"
        return f"<span style='display:inline-block;padding:1px 5px;border-radius:4px;background:{bg};color:#34D399;font-weight:700;font-size:11.5px;'>{sign}{v:.2f}%</span>"
    bg = "rgba(239, 68, 68, 0.24)" if v <= -10 else "rgba(239, 68, 68, 0.11)"
    return f"<span style='display:inline-block;padding:1px 5px;border-radius:4px;background:{bg};color:#F87171;font-weight:700;font-size:11.5px;'>{v:.2f}%</span>"


def rsi_badge_html(v):
    if v is None or pd.isna(v):
        return "<span style='color:#64748B;'>—</span>"
    if v >= 70:
        return f"<span style='display:inline-block;padding:1px 5px;border-radius:4px;background:rgba(239,68,68,0.16);color:#F87171;font-weight:700;font-size:11.5px;'>{v:.1f}</span>"
    if v <= 35:
        return f"<span style='display:inline-block;padding:1px 5px;border-radius:4px;background:rgba(16,185,129,0.16);color:#34D399;font-weight:700;font-size:11.5px;'>{v:.1f}</span>"
    return f"<span style='display:inline-block;padding:1px 5px;border-radius:4px;background:rgba(148,163,184,0.12);color:#E2E8F0;font-size:11.5px;'>{v:.1f}</span>"


def quartile_badge_html(q_text):
    q = q_text or "—"
    if "Q1" in q:
        return f"<span style='display:inline-block;padding:2px 7px;border-radius:4px;background:rgba(16,185,129,0.18);color:#34D399;font-weight:700;font-size:11px;'>{q}</span>"
    return f"<span style='display:inline-block;padding:2px 7px;border-radius:4px;background:rgba(245,158,11,0.18);color:#FBBF24;font-weight:700;font-size:11px;'>{q}</span>"


# --- HEADER + LAST FETCHED & FRESHNESS SIGNAL ---
regime = ai.get("market_regime", "Awaiting AI Sync")


def manual_status(m):
    raw = str(m.get("manual_data_asof", "")).strip()
    try:
        d = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=IST)
    except ValueError:
        return "not set", "status-stale", "MANUAL MACRO: date not set"
    age = (datetime.now(IST) - d).days
    if age > 35:
        return raw, "status-aging", f"MANUAL MACRO: {age}d old \u2014 update config.yaml"
    return raw, "status-fresh", f"MANUAL MACRO as of {raw}"


man_asof, man_css, man_label = manual_status(macro)
st.markdown(
    f"""
    <div class="brand-title">AURA BI AGENT</div>
    <div class="brand-sub">
        Last Fetched: <strong>{esc(last_fetched_str)}</strong> ({esc(fresh_detail)})
        <span class="{fresh_css}">{fresh_tag}</span>
        <span class="{man_css}">{esc(man_label)}</span>
        <span class="regime-pill">REGIME: {esc(regime.upper())}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

if "fetch_notice" in st.session_state and st.session_state["fetch_notice"]:
    kind, msg = st.session_state.pop("fetch_notice")
    getattr(st, kind)(msg)

if fresh_css == "status-stale":
    st.warning(
        f"⚠️ **Data Not Newly Updated:** Last successful fetch was **{last_fetched_str}** ({fresh_detail}). "
        "The scheduled GitHub Actions job may have failed or been delayed \u2014 check its latest run."
    )
elif fresh_css == "status-aging":
    st.info(
        f"🕒 **Aging Snapshot:** Last fetched at **{last_fetched_str}** ({fresh_detail}). "
        "The next scheduled run will refresh it."
    )

# --- HISTORY (appended by each scheduled run) ---
HISTORY_PATH = "data/history.jsonl"


@st.cache_data(show_spinner=False)
def _read_history(path, mtime):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return rows


history_rows = _read_history(HISTORY_PATH, os.path.getmtime(HISTORY_PATH)) if os.path.exists(HISTORY_PATH) else []


def hist_series(name):
    return [r["prices"][name] for r in history_rows if (r.get("prices") or {}).get(name) is not None]


def spark_svg(vals, w=88, h=22):
    if len(vals) < 3:
        return ""
    vals = vals[-30:]
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    pts = " ".join(f"{i * (w / (len(vals) - 1)):.1f},{h - 2 - ((v - lo) / rng) * (h - 4):.1f}" for i, v in enumerate(vals))
    color = "#34D399" if vals[-1] >= vals[0] else "#F87171"
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="margin-top:4px;"><polyline fill="none" stroke="{color}" stroke-width="1.5" points="{pts}"/></svg>'


# --- TOP KPI PULSE STRIP ---
def find_item(cat, keyword):
    for x in markets.get(cat, []):
        if keyword.lower() in x["name"].lower():
            return x
    return None

kpis = [
    ("Nifty 50", find_item("indian_equity", "Nifty 50")),
    ("BSE SENSEX", find_item("indian_equity", "SENSEX")),
    ("S&P 500", find_item("global_indices", "S&P 500")),
    ("Gold INR / 10g", find_item("macro_commodities_fx", "Gold INR")),
    ("USD / INR", find_item("macro_commodities_fx", "USD / INR")),
    ("India VIX", find_item("volatility_indices", "India VIX")),
]

kpi_cols = st.columns(4) + st.columns(4)
for idx, (label, item) in enumerate(kpis):
    with kpi_cols[idx]:
        if item:
            d1 = item.get("1D") or 0
            cls = "kpi-pos" if d1 >= 0 else "kpi-neg"
            sign = "+" if d1 > 0 else ""
            st.markdown(
                f"""
                <div class="kpi-card">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-val">{format_price(item)}</div>
                  <div class="{cls}">{sign}{d1:.2f}%</div>
                  {spark_svg(hist_series(item.get("name")))}
                </div>
                """,
                unsafe_allow_html=True,
            )

with kpi_cols[6]:
    fpi_val = float(flows.get("fpi_net_cr", 0))
    dii_val = float(flows.get("dii_net_cr", 0))
    fpi_cls = "kpi-pos" if fpi_val >= 0 else "kpi-neg"
    st.markdown(
        f"""
        <div class="kpi-card">
          <div class="kpi-label">FPI / DII (Cr)</div>
          <div class="kpi-val">₹{fpi_val:+,.0f}</div>
          <div class="{fpi_cls}">DII: ₹{dii_val:+,.0f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi_cols[7]:
    repo = macro.get("rbi_repo_rate", 6.50)
    gsec = macro.get("india_10y_gsec_approx", 6.85)
    spread = round(gsec - repo, 2)
    sprd_cls = "kpi-pos" if spread >= 0 else "kpi-neg"
    st.markdown(
        f"""
        <div class="kpi-card">
          <div class="kpi-label">RBI Repo / 10Y</div>
          <div class="kpi-val">{repo:.2f}%/{gsec:.2f}%</div>
          <div class="{sprd_cls}">{spread:+.2f}% Sprd</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- COMPACT AURA AI GUIDE ---
with st.expander("📘 AURA AI guide — Glossary, CAGR Formula & Desk view | reasoning"):
    g1, g2 = st.columns(2)
    with g1:
        st.markdown(
            """
            * **CAGR (3Y & 5Y):** `((Ending / Beginning) ^ (1 / Years)) - 1` annualized return rate.
            * **Std Dev (Vol %), Sharpe & Max DD:** Annualized return dispersion, excess return per unit of risk (`Rf = 6.8%`), and peak-to-trough 1Y drawdown.
            * **Downside Capture (%):** `< 100%` means the fund/sector fell less than Nifty 50 during market down days.
            """
        )
    with g2:
        st.markdown(
            """
            * **Nifty 10Y Valuation Check:** Compares current Nifty P/E, P/B, and Dividend Yield against 10Y averages (`22.5x`, `3.2x`, `1.35%`) to show the **valuation zone**.
            * **Relative Strength vs. Nifty:** Sector return minus Nifty 50 return over `1M` and `3M` to spot institutional rotation.
            * **Desk view | reasoning:** `Favourable`, `Neutral` or `Cautious` label from rules on trend, valuation and risk \u2014 a screening aid, not advice.
            """
        )

# --- COMPACT AI BRIEF ---
if ai:
    c1, c2 = st.columns(2)
    with c1:
        opp_md = "<br>".join(f"• {esc(x)}" for x in ai.get("opportunities", []))
        st.markdown(f'<div class="ai-box"><strong>🎯 BI Opportunities</strong><br>{opp_md}</div>', unsafe_allow_html=True)
    with c2:
        risk_md = "<br>".join(f"• {esc(x)}" for x in ai.get("risk_flags", []))
        st.markdown(f'<div class="ai-box"><strong>⚠️ Risk & Overextension Alerts</strong><br>{risk_md}</div>', unsafe_allow_html=True)
    st.info(f"**🏦 Debt & Macro Call:** {ai.get('debt_and_macro', 'N/A')}")


# --- COMPACT HEATMAP TABLE RENDERER ---
def render_heatmap(items, show_valuation=True, show_risk_metrics=True, show_yield=False):
    if not items:
        st.info("No data available in the current snapshot.")
        return

    headers = ["Asset", "Price", "1D", "1W", "1M", "3M", "1Y", "3Y", "5Y", "Std Dev"]
    if show_risk_metrics:
        headers.extend(["Sharpe", "Down Cap", "Max DD", "RSI"])
    headers.extend(["52W High", "200-DMA"])
    if show_valuation:
        headers.append("P/E")
    if show_yield:
        headers.append("Yield %")
    headers.append("Desk view | reasoning")

    def plain_num(v, fmt):
        if v is None or pd.isna(v):
            return "<span style='color:#64748B;'>—</span>"
        return fmt.format(v)

    body_rows = []
    for x in items:
        stance_val = x.get("bi_stance", "Hold | mixed signals")
        tds = [
            f"<td style='font-weight:600;color:#F8FAFC;white-space:nowrap;padding:6px 8px;'>{x['name']}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;font-weight:600;color:#F8FAFC;white-space:nowrap;padding:6px 8px;'>{format_price(x)}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(x.get('1D'))}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(x.get('1W'))}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(x.get('1M'))}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(x.get('3M'))}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(x.get('1Y'))}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(x.get('3Y_CAGR'))}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(x.get('5Y_CAGR'))}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{plain_num(x.get('volatility_1y'), '{:.1f}%')}</td>",
        ]
        if show_risk_metrics:
            tds.append(f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{plain_num(x.get('sharpe_1y'), '{:.2f}')}</td>")
            tds.append(f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{plain_num(x.get('downside_capture'), '{:.0f}%')}</td>")
            tds.append(f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(x.get('max_drawdown_1y'))}</td>")
            tds.append(f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{rsi_badge_html(x.get('rsi_14'))}</td>")
        tds.append(f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(x.get('from_52w_high'))}</td>")
        tds.append(f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(x.get('dist_200dma'))}</td>")
        if show_valuation:
            tds.append(f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{plain_num(x.get('pe'), '{:.1f}')}</td>")
        if show_yield:
            tds.append(f"<td style='font-family:\"JetBrains Mono\",monospace;color:#34D399;font-weight:700;white-space:nowrap;padding:6px 6px;'>{plain_num(x.get('div_yield'), '{:.2f}%')}</td>")
        tds.append(f"<td style='padding:6px 8px;'>{format_stance_cell(stance_val)}</td>")
        body_rows.append("<tr style='border-bottom:1px solid rgba(255,255,255,0.05);'>" + "".join(tds) + "</tr>")

    th_html = "".join(
        f"<th style='text-align:left;padding:7px 7px;color:#94A3B8;font-size:10px;text-transform:uppercase;letter-spacing:0.4px;border-bottom:1px solid rgba(255,255,255,0.12);white-space:nowrap;'>{h}</th>"
        for h in headers
    )
    table_html = (
        "<div style='overflow-x:auto;border:1px solid rgba(255,255,255,0.08);border-radius:10px;background:rgba(15,23,42,0.72);margin-bottom:8px;'>"
        "<table style='width:100%;border-collapse:collapse;font-size:12px;'>"
        f"<thead><tr>{th_html}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)


def render_fund_alpha_heatmap(items):
    if not items:
        return

    def plain_num(v, fmt):
        if v is None or pd.isna(v):
            return "<span style='color:#64748B;'>—</span>"
        return fmt.format(v)

    headers = [
        "ETF Proxy", "Tracks", "ETF 1Y", "Index 1Y",
        "Diff vs Index", "3Y CAGR", "Std Dev",
        "Sharpe", "Down Cap", "Max DD",
    ]
    th_html = "".join(
        f"<th style='text-align:left;padding:7px 7px;color:#94A3B8;font-size:10px;text-transform:uppercase;letter-spacing:0.4px;border-bottom:1px solid rgba(255,255,255,0.12);white-space:nowrap;'>{h}</th>"
        for h in headers
    )

    body_rows = []
    for r in items:
        tds = [
            f"<td style='font-weight:600;color:#F8FAFC;white-space:nowrap;padding:6px 8px;'>{r.get('fund', '—')}</td>",
            f"<td style='color:#CBD5E1;white-space:nowrap;padding:6px 8px;'>{r.get('category', '—')}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(r.get('fund_1y'))}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(r.get('bench_1y'))}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(r.get('alpha_vs_bench'))}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(r.get('fund_3y_cagr'))}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{plain_num(r.get('std_dev'), '{:.1f}%')}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{plain_num(r.get('sharpe'), '{:.2f}')}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{plain_num(r.get('downside_capture'), '{:.0f}%')}</td>",
            f"<td style='font-family:\"JetBrains Mono\",monospace;white-space:nowrap;padding:6px 6px;'>{pct_badge_html(r.get('max_dd'))}</td>",
        ]
        body_rows.append("<tr style='border-bottom:1px solid rgba(255,255,255,0.05);'>" + "".join(tds) + "</tr>")

    table_html = (
        "<div style='overflow-x:auto;border:1px solid rgba(255,255,255,0.08);border-radius:10px;background:rgba(15,23,42,0.72);margin-bottom:8px;'>"
        "<table style='width:100%;border-collapse:collapse;font-size:12px;'>"
        f"<thead><tr>{th_html}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)


# --- MAIN TABS ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Pulse, Valuation & Equity",
    "🧭 Sectors & YoY Charts",
    "⚡ What's Interesting & Industry",
    "📰 News & Regulatory",
    "🌍 Global, FX & REITs",
    "🏦 Indian Debt, Inflation & AMFI",
    "📈 Trends & Client Notes",
])

with tab1:
    col_flow, col_val = st.columns([1, 1.35])
    with col_flow:
        render_section_heading("Institutional Flows (FPI vs. DII Cash)", f"{flows.get('source', '\u2014')} \u00b7 {flows.get('as_of_date', '\u2014')}")
        fpi_v = float(flows.get("fpi_net_cr", 0))
        dii_v = float(flows.get("dii_net_cr", 0))
        net_v = float(flows.get("net_institutional_cr", fpi_v + dii_v))
        streak_d = int(flows.get("fpi_sell_streak_days", 0))
        flow_df = pd.DataFrame([
            {"Participant": "FPI / FII Net", "Net Flow (₹ Cr)": f"₹{fpi_v:+,.0f}", "Signal": f"{streak_d}d sell streak" if fpi_v < 0 else "Net buyer"},
            {"Participant": "DII Net", "Net Flow (₹ Cr)": f"₹{dii_v:+,.0f}", "Signal": "Domestic support" if dii_v > 0 else "Net seller"},
            {"Participant": "Combined Net", "Net Flow (₹ Cr)": f"₹{net_v:+,.0f}", "Signal": "Net liquidity positive" if net_v >= 0 else "Net institutional outflow"},
        ])
        st.dataframe(flow_df, width="stretch", hide_index=True)

    with col_val:
        render_section_heading("Nifty 50 Valuation vs. 10-Year Averages", as_of_stamp)
        nifty_row = find_item("indian_equity", "Nifty 50") or {}
        cur_pe = nifty_row.get("pe") or 22.0
        cur_pb = nifty_row.get("pb") or 3.3
        cur_dy = nifty_row.get("div_yield") or 1.25
        avg_pe = float(macro.get("nifty_10y_avg_pe", 22.5))
        avg_pb = float(macro.get("nifty_10y_avg_pb", 3.2))
        avg_dy = float(macro.get("nifty_10y_avg_div_yield", 1.35))
        eps_g = float(macro.get("nifty_eps_growth_yoy", 11.4))

        if cur_pe <= avg_pe * 0.92:
            deploy_call = "Valuation below 10Y avg"
        elif cur_pe <= avg_pe * 1.08:
            deploy_call = "Valuation near 10Y avg"
        else:
            deploy_call = "Valuation above 10Y avg"

        val_df = pd.DataFrame([
            {"Metric": "Nifty P/E", "Current": f"{cur_pe:.1f}x", "10Y Avg": f"{avg_pe:.1f}x", "Spread": f"{(cur_pe - avg_pe):+.1f}x"},
            {"Metric": "Nifty P/B", "Current": f"{cur_pb:.2f}x", "10Y Avg": f"{avg_pb:.2f}x", "Spread": f"{(cur_pb - avg_pb):+.2f}x"},
            {"Metric": "Dividend Yield", "Current": f"{cur_dy:.2f}%", "10Y Avg": f"{avg_dy:.2f}%", "Spread": f"{(cur_dy - avg_dy):+.2f}%"},
            {"Metric": "Earnings Growth", "Current": f"{eps_g:+.1f}% YoY", "10Y Avg": "11.0% YoY", "Spread": deploy_call},
            {"Metric": "Earnings yield vs 10Y G-Sec", "Current": f"{100 / cur_pe:.2f}% vs {float(macro.get('india_10y_gsec_approx', 6.85)):.2f}%", "10Y Avg": "\u2014", "Spread": f"{100 / cur_pe - float(macro.get('india_10y_gsec_approx', 6.85)):+.2f}%"},
        ])
        st.dataframe(val_df, width="stretch", hide_index=True)

    view_slice = st.radio(
        "Quick Focus",
        ["All", "Broad Equity & MF", "Fund Alpha & Risk", "Volatility"],
        horizontal=True,
    )
    if view_slice in ["All", "Broad Equity & MF"]:
        render_section_heading("Indian Broad Equity, BSE SENSEX & MF Benchmarks", as_of_stamp)
        render_heatmap(markets.get("indian_equity", []), show_valuation=True, show_risk_metrics=True)

    if view_slice in ["All", "Fund Alpha & Risk"]:
        render_section_heading("Index ETF Proxies vs Benchmark (tracking difference)", as_of_stamp)
        render_fund_alpha_heatmap(fund_alpha)

    if view_slice in ["All", "Volatility"]:
        render_section_heading("Volatility & Fear Indices", as_of_stamp)
        render_heatmap(markets.get("volatility_indices", []), show_valuation=False, show_risk_metrics=False)

with tab2:
    chart_mode = st.radio(
        "View",
        ["Sector Rotation, Leaders & Laggards", "YoY Returns Heatmap (Since 1995)"],
        horizontal=True,
    )

    if chart_mode == "Sector Rotation, Leaders & Laggards":
        render_section_heading("Sector Index Heatmap (1W, 1M, 3M, 1Y) & Relative Strength vs. Nifty", as_of_stamp)
        sectors = markets.get("indian_sectors", [])
        if sectors:
            nifty_item = find_item("indian_equity", "Nifty 50")
            nifty_1m = nifty_item.get("1M") if nifty_item and nifty_item.get("1M") is not None else 0.0
            nifty_3m = nifty_item.get("3M") if nifty_item and nifty_item.get("3M") is not None else 0.0
            nifty_1y = nifty_item.get("1Y") if nifty_item and nifty_item.get("1Y") is not None else 0.0

            matrix_rows = []
            for x in sectors:
                r1w = x.get("1W")
                r1m = x.get("1M")
                r3m = x.get("3M")
                r1y = x.get("1Y")
                rel_1m = round(r1m - nifty_1m, 2) if r1m is not None else None
                rel_3m = round(r3m - nifty_3m, 2) if r3m is not None else None
                rel_1y = round(r1y - nifty_1y, 2) if r1y is not None else None

                if rel_3m is not None and rel_3m >= 3.0 and (r1m is not None and r1m >= 0):
                    bucket = "Leader"
                elif rel_3m is not None and rel_3m <= -3.0:
                    bucket = "Laggard"
                else:
                    bucket = "In-Line"

                matrix_rows.append({
                    "Sector": x["name"],
                    "1W": pct_badge_html(r1w),
                    "1M": pct_badge_html(r1m),
                    "3M": pct_badge_html(r3m),
                    "1Y": pct_badge_html(r1y),
                    "RS vs Nifty 1M": pct_badge_html(rel_1m),
                    "RS vs Nifty 3M": pct_badge_html(rel_3m),
                    "RS vs Nifty 1Y": pct_badge_html(rel_1y),
                    "RSI": rsi_badge_html(x.get("rsi_14")),
                    "P/E": f"{x['pe']:.1f}" if x.get("pe") is not None else "—",
                    "Status": bucket,
                    "Desk view | reasoning": format_stance_cell(x.get("bi_stance", "Hold | mixed signals")),
                    "talking_point": x.get("talking_point", ""),
                    "_sort_3m": rel_3m if rel_3m is not None else -9999.0,
                })

            mdf = pd.DataFrame(matrix_rows).sort_values("_sort_3m", ascending=False)

            top2 = mdf.head(2)
            bot2 = mdf.tail(2)
            c_top, c_bot = st.columns(2)
            with c_top:
                lines = "<br>".join(f"• <strong>{r['Sector']}</strong>: {esc(r['talking_point'])}" for _, r in top2.iterrows())
                st.markdown(f'<div class="ai-box"><strong>🚀 Top Sectors — Client Talking Points</strong><br>{lines}</div>', unsafe_allow_html=True)
            with c_bot:
                lines = "<br>".join(f"• <strong>{r['Sector']}</strong>: {esc(r['talking_point'])}" for _, r in bot2.iterrows())
                st.markdown(f'<div class="ai-box"><strong>📉 Bottom Sectors — Client Talking Points</strong><br>{lines}</div>', unsafe_allow_html=True)

            disp_df = mdf.drop(columns=["_sort_3m", "talking_point"])
            m_headers = list(disp_df.columns)
            m_ths = "".join(
                f"<th style='text-align:left;padding:7px 7px;color:#94A3B8;font-size:10px;text-transform:uppercase;border-bottom:1px solid rgba(255,255,255,0.12);white-space:nowrap;'>{h}</th>"
                for h in m_headers
            )
            m_trs = []
            for _, r in disp_df.iterrows():
                cells = [
                    f"<td style='font-weight:600;color:#F8FAFC;white-space:nowrap;padding:6px 8px;'>{r['Sector']}</td>",
                    f"<td style='font-family:\"JetBrains Mono\",monospace;padding:6px 6px;'>{r['1W']}</td>",
                    f"<td style='font-family:\"JetBrains Mono\",monospace;padding:6px 6px;'>{r['1M']}</td>",
                    f"<td style='font-family:\"JetBrains Mono\",monospace;padding:6px 6px;'>{r['3M']}</td>",
                    f"<td style='font-family:\"JetBrains Mono\",monospace;padding:6px 6px;'>{r['1Y']}</td>",
                    f"<td style='font-family:\"JetBrains Mono\",monospace;padding:6px 6px;'>{r['RS vs Nifty 1M']}</td>",
                    f"<td style='font-family:\"JetBrains Mono\",monospace;padding:6px 6px;'>{r['RS vs Nifty 3M']}</td>",
                    f"<td style='font-family:\"JetBrains Mono\",monospace;padding:6px 6px;'>{r['RS vs Nifty 1Y']}</td>",
                    f"<td style='font-family:\"JetBrains Mono\",monospace;padding:6px 6px;'>{r['RSI']}</td>",
                    f"<td style='font-family:\"JetBrains Mono\",monospace;color:#E2E8F0;padding:6px 6px;'>{r['P/E']}</td>",
                    f"<td style='color:#CBD5E1;font-weight:600;padding:6px 7px;'>{r['Status']}</td>",
                    f"<td style='padding:6px 8px;'>{r['Desk view | reasoning']}</td>",
                ]
                m_trs.append("<tr style='border-bottom:1px solid rgba(255,255,255,0.05);'>" + "".join(cells) + "</tr>")

            st.markdown(
                "<div style='overflow-x:auto;border:1px solid rgba(255,255,255,0.08);border-radius:10px;background:rgba(15,23,42,0.72);margin-bottom:12px;'>"
                f"<table style='width:100%;border-collapse:collapse;font-size:12px;'><thead><tr>{m_ths}</tr></thead><tbody>{''.join(m_trs)}</tbody></table></div>",
                unsafe_allow_html=True,
            )

            q_items = []
            for x in sectors:
                if x.get("dist_200dma") is not None and x.get("3M") is not None:
                    bkt, head, reason = split_stance(x.get("bi_stance"))
                    q_items.append({
                        "Sector": x["name"],
                        "Trend vs 200-DMA (%)": x["dist_200dma"],
                        "3M Return (%)": x["3M"],
                        "Stance": bkt,
                        "Summary": f"{head} — {reason}" if reason else head,
                    })

            if q_items:
                qdf = pd.DataFrame(q_items)
                color_map = {"Buy": "#10B981", "Hold": "#F59E0B", "Sell": "#EF4444"}
                fig = go.Figure()
                for bkt in ["Buy", "Hold", "Sell"]:
                    sub = qdf[qdf["Stance"] == bkt]
                    if sub.empty:
                        continue
                    fig.add_trace(
                        go.Scatter(
                            x=sub["Trend vs 200-DMA (%)"],
                            y=sub["3M Return (%)"],
                            mode="markers+text",
                            name=STANCE_LABELS[bkt],
                            text=sub["Sector"],
                            textposition="top center",
                            customdata=sub[["Summary", "3M Return (%)", "Trend vs 200-DMA (%)"]],
                            marker={"size": 14, "color": color_map[bkt], "line": {"width": 1.5, "color": "#0F172A"}},
                            hovertemplate=(
                                "<b>%{text}</b><br>"
                                "View: %{customdata[0]}<br>"
                                "3M Move: %{customdata[1]:+.1f}%<br>"
                                "Vs 200-DMA: %{customdata[2]:+.1f}%<extra></extra>"
                            ),
                        )
                    )
                fig.add_vline(x=0, line_dash="dash", line_color="#64748B")
                fig.add_hline(y=0, line_dash="dash", line_color="#64748B")
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(17,25,40,0.5)",
                    xaxis_title="Distance from 200-DMA (%)",
                    yaxis_title="3-Month Return (%)",
                    height=350,
                    margin={"l": 10, "r": 10, "t": 20, "b": 30},
                )
                st.plotly_chart(fig, width="stretch")

    else:
        render_section_heading("Year-on-Year Returns Heatmap (1995–Present)", as_of_stamp)
        yoy_candidates = [x for x in (markets.get("indian_equity", []) + markets.get("global_indices", [])) if x.get("yoy_returns")]
        if yoy_candidates:
            selected_indices = st.multiselect(
                "Compare Indices",
                options=[x["name"] for x in yoy_candidates],
                default=[x["name"] for x in yoy_candidates[:3]],
            )
            chosen_list = [x for x in yoy_candidates if x["name"] in selected_indices] or [yoy_candidates[0]]
            all_years = sorted({yr for x in chosen_list for yr in x.get("yoy_returns", {}).keys()})

            if all_years:
                z_vals, text_vals, y_labels = [], [], []
                for x in chosen_list:
                    y_labels.append(x["name"])
                    row_z, row_t = [], []
                    ymap = x.get("yoy_returns", {})
                    for yr in all_years:
                        val = ymap.get(yr)
                        if val is None:
                            row_z.append(np.nan)
                            row_t.append("—")
                        else:
                            row_z.append(val)
                            row_t.append(f"{val:+.0f}%")
                    z_vals.append(row_z)
                    text_vals.append(row_t)

                hm_fig = go.Figure(
                    data=go.Heatmap(
                        z=z_vals,
                        x=all_years,
                        y=y_labels,
                        text=text_vals,
                        texttemplate="%{text}",
                        textfont={"size": 10},
                        colorscale=[[0.0, "#991B1B"], [0.45, "#1E293B"], [1.0, "#059669"]],
                        zmid=0,
                        colorbar={"title": "YoY %"},
                        hovertemplate="<b>%{y}</b> (%{x})<br>Annual Return: <b>%{text}</b><extra></extra>",
                    )
                )
                hm_fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(17,25,40,0.5)",
                    height=max(240, 95 + len(y_labels) * 55),
                    margin={"l": 10, "r": 10, "t": 20, "b": 30},
                )
                st.plotly_chart(hm_fig, width="stretch")

with tab3:
    render_section_heading("What's Interesting Today — Rules-Based Market Signals", as_of_stamp)
    if whats_interesting:
        a_cols = st.columns(2)
        for idx, al in enumerate(whats_interesting):
            sev = al.get("severity", "WATCH")
            border_c = "#EF4444" if sev == "ALERT" else ("#10B981" if sev == "OK" else "#F59E0B")
            with a_cols[idx % 2]:
                st.markdown(
                    f"""
                    <div class="alert-card" style="border-left: 3px solid {border_c};">
                      <span class="badge" style="color:{border_c};">{sev}</span>
                      <strong style="color:#F8FAFC;font-size:13.5px;">{esc(al.get('title', ''))}</strong>
                      <div style="font-size:12px;color:#94A3B8;margin-top:3px;">{esc(al.get('detail', ''))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    render_section_heading(f"AMFI Industry Flows & Retail Pulse ({amfi_monthly.get('report_month', 'Monthly')})", as_of_stamp)
    if amfi_monthly:
        i1, i2, i3, i4, i5 = st.columns(5)
        i1.metric("Monthly SIP Inflow", f"₹{amfi_monthly.get('monthly_sip_inflow_cr', 0):,} Cr")
        i2.metric("Equity Net Inflow", f"₹{amfi_monthly.get('equity_net_inflow_cr', 0):,} Cr")
        i3.metric("Industry AUM", f"₹{amfi_monthly.get('industry_aum_lakh_cr', 0):.1f} L Cr")
        i4.metric("Total Folios", f"{amfi_monthly.get('total_folios_cr', 0):.1f} Cr")
        i5.metric("Leading Category", amfi_monthly.get("top_category_inflow", "Flexi Cap"))

    render_section_heading("NFO Calendar & Screening Flags", as_of_stamp)
    if nfo_watchlist:
        nfo_df = pd.DataFrame(nfo_watchlist).rename(columns={
            "name": "NFO Scheme / Theme",
            "category": "Category",
            "flag": "Desk Flag",
            "reason": "Screening Rationale",
        })
        st.dataframe(nfo_df, width="stretch", hide_index=True)

with tab4:
    render_section_heading("News Headlines & SEBI / AMC Regulatory Feed", as_of_stamp)
    filter_reg = st.radio("Filter Feed", ["ALL", "INDIA", "GLOBAL", "REGULATORY"], horizontal=True)
    news_list = snapshot.get("verified_news", [])
    reg_raw = snapshot.get("raw_news", {}).get("regulatory", [])

    if filter_reg == "REGULATORY":
        if not reg_raw:
            st.info("No SEBI/AMC regulatory RSS items in the current snapshot.")
        for r in reg_raw:
            st.markdown(
                f"""
                <div class="news-card">
                  <span class="badge">SEBI / AMC</span>
                  <a href="{esc(safe_link(r.get('link')))}" target="_blank" style="color:#F8FAFC;font-weight:600;text-decoration:none;font-size:14.5px;">
                    {esc(r.get('title', ''))}
                  </a>
                  <div style="font-size:12px;color:#94A3B8;margin-top:4px;"><em>{esc(r.get('source', ''))} — {esc(r.get('published', ''))}</em></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        if not news_list:
            st.info("No news headlines in the current snapshot.")
        for n in news_list:
            if filter_reg != "ALL" and n.get("region", "").upper() != filter_reg:
                continue
            st.markdown(
                f"""
                <div class="news-card">
                  <span class="badge">{esc(n.get('region', ''))}</span>
                  <span class="badge">{esc(n.get('tag', ''))}</span>
                  <a href="{esc(safe_link(n.get('link')))}" target="_blank" style="color:#F8FAFC;font-weight:600;text-decoration:none;font-size:14.5px;">
                    {esc(n.get('title', ''))}
                  </a>
                  <div style="font-size:12.5px;color:#94A3B8;margin-top:4px;">
                    {esc(n.get('impact', ''))} <em>— {esc(n.get('source', ''))}</em>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with tab5:
    render_section_heading("Global Markets", as_of_stamp)
    render_heatmap(markets.get("global_indices", []), show_valuation=True, show_risk_metrics=True)

    render_section_heading("Gold, Currencies & Commodities", as_of_stamp)
    render_heatmap(markets.get("macro_commodities_fx", []), show_valuation=False, show_risk_metrics=True)

    render_section_heading("Indian REITs & InvITs (Prices & Distribution Yields)", as_of_stamp)
    render_heatmap(markets.get("reits_invits", []), show_valuation=False, show_risk_metrics=False, show_yield=True)

with tab6:
    render_section_heading("Indian Debt Yields, Inflation (CPI & WPI) & Sovereign Curve", f"MANUAL \u00b7 as of {man_asof}")
    repo = float(macro.get("rbi_repo_rate", 6.50))
    tbill_3m = float(macro.get("india_3m_tbill_approx", 6.55))
    gsec_1y = float(macro.get("india_1y_gsec_approx", 6.65))
    gsec_5y = float(macro.get("india_5y_gsec_approx", 6.75))
    gsec_10y = float(macro.get("india_10y_gsec_approx", 6.85))
    cpi_now = float(macro.get("cpi_yoy_pct", 4.85))
    cpi_prev = float(macro.get("cpi_prev_pct", 5.10))
    wpi_now = float(macro.get("wpi_yoy_pct", 2.10))
    wpi_prev = float(macro.get("wpi_prev_pct", 1.85))
    real_rate = round(repo - cpi_now, 2)
    spread = round(gsec_10y - repo, 2)

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("RBI Repo Rate", f"{repo:.2f}%")
    m2.metric("India 10Y G-Sec", f"{gsec_10y:.2f}%", f"{spread:+.2f}% vs Repo")
    m3.metric("CPI Inflation (YoY)", f"{cpi_now:.2f}%", f"{(cpi_now - cpi_prev):+.2f}% MoM", delta_color="inverse")
    m4.metric("WPI Inflation (YoY)", f"{wpi_now:.2f}%", f"{(wpi_now - wpi_prev):+.2f}% MoM", delta_color="inverse")
    m5.metric("Real Policy Rate", f"{real_rate:+.2f}%", "Repo minus CPI")
    m6.metric("Duration Stance", "Short / Accrual" if spread < 0.5 else "Selective Gilt")

    c_left, c_right = st.columns([1, 1.35])
    with c_left:
        curve_df = pd.DataFrame([
            {"Tenor": "RBI Repo", "Yield %": repo},
            {"Tenor": "3M T-Bill", "Yield %": tbill_3m},
            {"Tenor": "1Y G-Sec", "Yield %": gsec_1y},
            {"Tenor": "5Y G-Sec", "Yield %": gsec_5y},
            {"Tenor": "10Y G-Sec", "Yield %": gsec_10y},
        ])
        curve_fig = px.line(
            curve_df,
            x="Tenor",
            y="Yield %",
            markers=True,
            labels={"Yield %": "Yield (%)"},
            template="plotly_dark",
            height=260,
        )
        curve_fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,25,40,0.5)")
        st.plotly_chart(curve_fig, width="stretch")

    with c_right:
        render_section_heading("Rates + Inflation Debt Positioning Matrix", as_of_stamp)
        domestic_matrix = pd.DataFrame([
            {"Category": "Liquid / Overnight", "Duration": "<91d", "Rate + CPI Fit": "High", "Role": "Cash & liquidity"},
            {"Category": "Money Market / Low Dur.", "Duration": "6m–1.5y", "Rate + CPI Fit": "High", "Role": "Captures elevated short rates"},
            {"Category": "Short Duration / Accrual", "Duration": "1–3y", "Rate + CPI Fit": "Overweight", "Role": "Best risk-adjusted carry when curve is flat"},
            {"Category": "Corporate / Banking & PSU", "Duration": "2–5y", "Rate + CPI Fit": "Accumulate", "Role": "AAA spread pickup over G-Secs"},
            {"Category": "Gilt / Long Duration", "Duration": "7–10y+", "Rate + CPI Fit": "Tactical", "Role": "Play on CPI cooling & RBI rate-cut cycle"},
        ])
        st.dataframe(domestic_matrix, width="stretch", hide_index=True)

    render_section_heading("AMFI Indian Debt & Liquid Mutual Fund NAVs", as_of_stamp)
    if amfi_debt_schemes:
        adf = pd.DataFrame(amfi_debt_schemes).rename(columns={
            "scheme_name": "AMFI Scheme (Growth)",
            "bucket": "Category",
            "duration": "Duration",
            "credit": "Credit",
            "nav": "NAV (₹)",
            "nav_date": "NAV Date",
        })
        st.dataframe(
            adf.style.format({"NAV (₹)": "₹{:.4f}"}),
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption(
            "AMFI live NAV feed returned empty on this run (often due to AMFI portal restrictions on cloud servers). "
            "Sovereign yield benchmarks, CPI/WPI inflation metrics, and category duration profiles above remain active."
        )

with tab7:
    # ---- 1. since previous snapshot
    render_section_heading("Since the Previous Session", "from stored history")
    if len(history_rows) >= 2:
        prev_r, last_r = history_rows[-2], history_rows[-1]
        diff_keys = ["Nifty 50", "BSE SENSEX", "Nifty Midcap 150", "Gold INR / 10g", "USD / INR", "Brent Crude", "India VIX", "US 10Y Treasury Yield"]
        diff_rows = []
        for k in diff_keys:
            a, b = (prev_r.get("prices") or {}).get(k), (last_r.get("prices") or {}).get(k)
            if a and b:
                diff_rows.append({"Instrument": k, "Previous": f"{a:,.2f}", "Latest": f"{b:,.2f}", "Change": f"{(b / a - 1) * 100:+.2f}%"})
        if diff_rows:
            st.dataframe(pd.DataFrame(diff_rows), width="stretch", hide_index=True)
    else:
        st.info("History builds up with each scheduled run. Comparisons appear after two sessions.")

    # ---- 2. flows chart + valuation percentile
    f_col, v_col = st.columns([1.6, 1])
    with f_col:
        render_section_heading("FPI vs DII \u2014 last 20 sessions (\u20b9 Cr)", "from stored history")
        flow_rows = [
            {"Date": r.get("flow_date"), "FPI": r["flows"]["fpi_net_cr"], "DII": r["flows"]["dii_net_cr"]}
            for r in history_rows[-20:]
            if (r.get("flows") or {}).get("fpi_net_cr") is not None and (r.get("flows") or {}).get("dii_net_cr") is not None
        ]
        if len(flow_rows) >= 2:
            fdf = pd.DataFrame(flow_rows)
            ffig = go.Figure()
            ffig.add_bar(x=fdf["Date"], y=fdf["FPI"], name="FPI", marker_color="#E2C06D")
            ffig.add_bar(x=fdf["Date"], y=fdf["DII"], name="DII", marker_color="#38BDF8")
            ffig.update_layout(template="plotly_dark", barmode="group", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,25,40,0.5)", height=280, margin={"l": 10, "r": 10, "t": 10, "b": 30})
            st.plotly_chart(ffig, width="stretch")
        else:
            st.caption("The flow chart appears after two or more stored sessions.")
    with v_col:
        render_section_heading("Nifty P/E vs own history", "from stored history")
        pe_hist = [(r.get("pe") or {}).get("Nifty 50") for r in history_rows]
        pe_hist = [x for x in pe_hist if x]
        if len(pe_hist) >= 30:
            pctl = float((np.array(pe_hist) <= pe_hist[-1]).mean() * 100)
            st.metric("P/E percentile", f"{pctl:.0f}th", f"{len(pe_hist)} sessions of history")
        else:
            st.metric("P/E percentile", "building\u2026", f"{len(pe_hist)}/30 sessions")
            st.caption("Unlocks once 30 sessions are stored. It will rank today's P/E against the terminal's own record.")

    # ---- 3. asset class scoreboard
    render_section_heading("Asset-Class Scoreboard (who is ahead)", as_of_stamp)
    asset_defs = [
        ("Nifty 50", "indian_equity", "Nifty 50"), ("Midcap 150", "indian_equity", "Midcap 150"),
        ("Smallcap 250", "indian_equity", "Smallcap 250"), ("Gold (INR)", "macro_commodities_fx", "Gold INR"),
        ("Silver (USD)", "macro_commodities_fx", "Silver"), ("Brent Crude", "macro_commodities_fx", "Brent"),
        ("USD / INR", "macro_commodities_fx", "USD / INR"), ("MSCI EM", "global_indices", "MSCI"),
        ("S&P 500", "global_indices", "S&P 500"),
    ]
    cols_def = [("1M", "1M"), ("3M", "3M"), ("1Y", "1Y"), ("3Y CAGR", "3Y_CAGR")]
    z, txt, ylab = [], [], []
    for label, cat, kw in asset_defs:
        it = find_item(cat, kw)
        if not it:
            continue
        ylab.append(label)
        zr, tr = [], []
        for _, key in cols_def:
            v = it.get(key)
            zr.append(np.nan if v is None else v)
            tr.append("\u2014" if v is None else f"{v:+.1f}%")
        z.append(zr)
        txt.append(tr)
    if z:
        sfig = go.Figure(go.Heatmap(z=z, x=[c[0] for c in cols_def], y=ylab, text=txt, texttemplate="%{text}", colorscale=[[0.0, "#991B1B"], [0.5, "#1E293B"], [1.0, "#059669"]], zmid=0, showscale=False))
        sfig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,25,40,0.5)", height=max(260, 60 + 34 * len(ylab)), margin={"l": 10, "r": 10, "t": 10, "b": 20}, yaxis={"autorange": "reversed"})
        st.plotly_chart(sfig, width="stretch")
        st.caption("USD / INR up = rupee weaker. Commodity rows are in USD unless labelled INR.")

    # ---- 4. sector rotation quadrant (relative strength 3M vs 1M)
    render_section_heading("Sector Rotation Quadrant (relative to Nifty 50)", as_of_stamp)
    n_it = find_item("indian_equity", "Nifty 50") or {}
    quad_pts = []
    for x in markets.get("indian_sectors", []):
        if x.get("1M") is None or x.get("3M") is None:
            continue
        rs3 = x["3M"] - (n_it.get("3M") or 0.0)
        rs1 = x["1M"] - (n_it.get("1M") or 0.0)
        quad = "Leading" if (rs3 >= 0 and rs1 >= 0) else "Weakening" if (rs3 >= 0 and rs1 < 0) else "Improving" if (rs3 < 0 and rs1 >= 0) else "Lagging"
        quad_pts.append({"Sector": x["name"], "RS 3M": round(rs3, 2), "RS 1M": round(rs1, 2), "Quadrant": quad})
    if quad_pts:
        qd = pd.DataFrame(quad_pts)
        qcol = {"Leading": "#10B981", "Weakening": "#F59E0B", "Improving": "#38BDF8", "Lagging": "#EF4444"}
        qfig = go.Figure()
        for qn, c in qcol.items():
            sub = qd[qd["Quadrant"] == qn]
            if sub.empty:
                continue
            qfig.add_trace(go.Scatter(x=sub["RS 3M"], y=sub["RS 1M"], mode="markers+text", text=sub["Sector"], textposition="top center", name=qn, marker={"size": 13, "color": c, "line": {"width": 1.2, "color": "#0F172A"}}))
        qfig.add_vline(x=0, line_dash="dash", line_color="#64748B")
        qfig.add_hline(y=0, line_dash="dash", line_color="#64748B")
        qfig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,25,40,0.5)", xaxis_title="3M return minus Nifty 50 (pp)", yaxis_title="1M return minus Nifty 50 (pp)", height=380, margin={"l": 10, "r": 10, "t": 10, "b": 30})
        st.plotly_chart(qfig, width="stretch")

    # ---- 5. client note drafts (neutral, templated, review before sending)
    render_section_heading("Client Note Drafts (review before sending)", "template-based, from today's data")
    usd = find_item("macro_commodities_fx", "USD / INR") or {}
    gbp = find_item("macro_commodities_fx", "GBP / INR") or {}
    eur = find_item("macro_commodities_fx", "EUR / INR") or {}
    nf = find_item("indian_equity", "Nifty 50") or {}
    vx = find_item("volatility_indices", "India VIX") or {}
    sip_cr = amfi_monthly.get("monthly_sip_inflow_cr")
    repo_v = float(macro.get("rbi_repo_rate", 0) or 0)
    g10_v = float(macro.get("india_10y_gsec_approx", 0) or 0)

    def _fx(it, nm):
        return f"{nm} {it['price']:.2f} ({it.get('1M', 0) or 0:+.1f}% in 1M)" if it.get("price") else ""

    fx_line = ", ".join(x for x in [_fx(usd, "USD/INR"), _fx(gbp, "GBP/INR"), _fx(eur, "EUR/INR")] if x)
    note_nri = (
        f"Market note for NRIs: {fx_line or 'currency data not available'}. Nifty 50 is {nf.get('1Y', 0) or 0:+.1f}% over 1 year. "
        "Exchange-rate moves affect your INR returns when converted back, so investing in regular instalments over a long horizon avoids timing a single exchange rate."
    )
    note_ret = (
        f"Market note: RBI repo {repo_v:.2f}%, 10-year G-Sec about {g10_v:.2f}%. Equity volatility (India VIX {vx.get('price', 0) or 0:.1f}) is a reminder to keep money you need in the next few years in lower-risk categories, "
        "and to enter equity gradually rather than in one go."
    )
    note_new = (
        f"Did you know? Industry SIP inflows were about \u20b9{(sip_cr or 0):,} Cr in {amfi_monthly.get('report_month', 'the latest month')} \u2014 lakhs of investors invest the same amount every month regardless of headlines. "
        f"Nifty 50 P/E is {nf.get('pe', 0) or 0:.1f}x against a 10-year average of {float(macro.get('nifty_10y_avg_pe', 0) or 0):.1f}x. A SIP spreads your entry across market highs and lows."
    )
    for ttl, body in [("NRI / returning NRI", note_nri), ("Retirement seekers", note_ret), ("First-time investors", note_new)]:
        st.caption(ttl)
        st.code(body + "\n\n" + DISCLAIMER, language=None)

with st.expander("📎 Appendix — Data Sources, Proxies & Refresh Cadence"):
    sources_df = pd.DataFrame([
        {"Module": "Indian Equity, SENSEX & Sectors", "Primary Source": "Yahoo Finance (NSE/BSE Index & ETF Proxies)", "Cadence": "Automated 8:30 AM & 4:30 PM IST"},
        {"Module": "Institutional Flows (FPI / DII)", "Primary Source": "NSE Cash Market API (fiidiiTradeReact) + Desk Fallback", "Cadence": "Daily EOD / On Refresh"},
        {"Module": "Nifty Valuation (10Y P/E, P/B, Yield)", "Primary Source": "ETF Trailing Multiples + 10-Year Historical Anchors", "Cadence": "Daily / Quarterly Earnings Update"},
        {"Module": "Indian REITs & InvITs", "Primary Source": "Yahoo Finance NSE Listings (Embassy, Mindspace, Brookfield, Nexus, IndiGrid, PowerGrid)", "Cadence": "Daily / On Refresh"},
        {"Module": "Indian Debt, Sovereign Curve & Inflation", "Primary Source": "RBI Policy Rate, G-Sec Benchmarks & MoSPI CPI / WPI Anchors", "Cadence": "Monthly CPI/WPI & Policy Cycle"},
        {"Module": "Mutual Fund NAVs & Industry AUM/SIP", "Primary Source": "AMFI Official Portal (NAVAll.txt) & AMFI Monthly Flash", "Cadence": "Daily NAVs / Monthly Industry Data"},
        {"Module": "News & Regulatory Feed", "Primary Source": "SEBI RSS, LiveMint, Economic Times, Business Standard, CNBC, MarketWatch", "Cadence": "Continuous / On Refresh"},
    ])
    st.dataframe(sources_df, width="stretch", hide_index=True)

dh = snapshot.get("data_health", {})
st.caption(
    f"Data health: {dh.get('tickers_fetched', '?')}/{dh.get('tickers_expected', '?')} instruments \u00b7 "
    f"{dh.get('amfi_nav_rows', '?')} AMFI NAV rows \u00b7 {dh.get('news_items', '?')} news items \u00b7 flows: {dh.get('flows_source', '?')}"
)
st.caption(DISCLAIMER)
