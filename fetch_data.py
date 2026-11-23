import os
import re
import json
import yaml
import feedparser
import numpy as np
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
AMFI_NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"

VALUATION_PROXIES = {
    "^NSEI": ["NIFTYBEES.NS"],
    "^BSESN": ["SENSEXADD.NS", "NIFTYBEES.NS"],
    "^NSMIDCP": ["JUNIORBEES.NS"],
    "^NSEMDCP150": ["MID150BEES.NS"],
    "^CRSLDX": ["MONIFTY500.NS"],
    "^NSEBANK": ["BANKBEES.NS"],
    "^CNXPSUBANK": ["PSUBNKBEES.NS"],
    "^CNXIT": ["ITBEES.NS"],
    "^CNXPHARMA": ["PHARMABEES.NS", "HEALTHY.NS", "AXISHCETF.NS"],
    "^CNXINFRA": ["INFRABEES.NS"],
    "^CNXAUTO": ["AUTOBEES.NS"],
    "^CNXFMCG": ["FMCGIETF.NS", "CONSUMBEES.NS", "AXISCONSUM.NS"],
    "^CNXMETAL": ["METALIETF.NS"],
    "^CNXENERGY": ["OILIETF.NS"],
    "^GSPC": ["SPY"],
    "^DJI": ["DIA"],
    "^NDX": ["QQQ"],
    "^FTSE": ["EWU"],
    "^FCHI": ["EWQ"],
    "^N225": ["EWJ"],
    "^GDAXI": ["EWG"],
    "^HSI": ["EWH"],
}

# Representative ETF/Fund proxies to measure Fund vs Benchmark & Category Median Alpha
EQUITY_FUND_PROXIES = [
    {"fund": "Nippon India ETF Nifty BeES", "ticker": "NIFTYBEES.NS", "category": "Nifty 50", "benchmark_ticker": "^NSEI"},
    {"fund": "Nippon India ETF Junior BeES", "ticker": "JUNIORBEES.NS", "category": "Nifty Next 50", "benchmark_ticker": "^NSMIDCP"},
    {"fund": "Motilal Oswal Nifty Midcap 150 ETF", "ticker": "MID150BEES.NS", "category": "Midcap 150", "benchmark_ticker": "^NSEMDCP150"},
    {"fund": "Motilal Oswal Nifty 500 ETF", "ticker": "MONIFTY500.NS", "category": "Nifty 500", "benchmark_ticker": "^CRSLDX"},
]

AMFI_DEBT_BUCKETS = [
    {"bucket": "Liquid", "keywords": ["liquid fund"], "duration": "Ultra-Short (<91d)", "credit": "Sovereign / AAA"},
    {"bucket": "Money Market", "keywords": ["money market"], "duration": "Short (<1y)", "credit": "AAA / Commercial"},
    {"bucket": "Short Duration", "keywords": ["short duration", "short term"], "duration": "Short (1–3y)", "credit": "AAA / Sovereign"},
    {"bucket": "Corporate Bond", "keywords": ["corporate bond"], "duration": "Medium (2–5y)", "credit": "High-Grade AAA"},
    {"bucket": "Gilt / Long Duration", "keywords": ["gilt fund", "long duration"], "duration": "Long (7–10y+)", "credit": "Sovereign"},
]

SECTOR_TALKING_POINTS = {
    "Nifty Bank": ("Credit growth & NIM stability driving institutional inflows.", "Rate-cut margin pressure or PSU/private rotation weighing on banks."),
    "Nifty IT": ("US tech spending recovery & INR depreciation tailwind.", "Soft discretionary global IT budgets & cautious deal ramp-ups."),
    "Nifty Pharma": ("US generics pricing stability & domestic chronic care demand.", "USFDA inspection overhangs & profit booking after strong run."),
    "Nifty Auto": ("Rural two-wheeler recovery & SUV mix boosting margins.", "Inventory buildup in passenger vehicles & input cost watch."),
    "Nifty FMCG": ("Rural volume uptick & easing raw material inflation.", "Urban demand slowdown & rich valuation multiples."),
    "Nifty Metals": ("China stimulus hopes & domestic steel/aluminium demand.", "Global commodity price softness & tariff headwinds."),
    "Nifty Realty": ("Strong luxury pre-sales & low developer leverage.", "High valuation multiples & rate sensitivity."),
    "Nifty Energy": ("Power demand surge & refining/marketing margin recovery.", "Crude volatility & regulatory windfall/pricing risks."),
    "Nifty PSU Bank": ("Clean balance sheets, high RoA & cheap P/B re-rating.", "Profit booking after sharp multi-year rally & treasury MTM watch."),
    "Nifty Infra": ("Government capex execution & order-book visibility.", "Execution delays & stretched capital-goods multiples."),
}


def clean_label(text):
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def calc_cagr(start_price, end_price, years):
    if start_price is None or end_price is None or pd.isna(start_price) or pd.isna(end_price) or start_price <= 0 or years <= 0:
        return None
    return round(((end_price / start_price) ** (1 / years) - 1) * 100, 2)


def calc_ny_cagr(series, years):
    if series is None or len(series) < 20 or years <= 0:
        return None
    s = series.copy()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    s = s.sort_index()

    end_dt = s.index[-1]
    end_price = float(s.iloc[-1])
    target_dt = end_dt - pd.Timedelta(days=int(round(years * 365.25)))

    if s.index[0] > (target_dt + pd.Timedelta(days=45)):
        return None

    past_slice = s[s.index <= target_dt]
    if past_slice.empty:
        return None

    start_price = float(past_slice.iloc[-1])
    actual_years = (end_dt - past_slice.index[-1]).days / 365.25
    if actual_years < (years * 0.85):
        return None

    return calc_cagr(start_price, end_price, actual_years)


def calc_pct_return(series, trading_days):
    if len(series) <= trading_days:
        return None
    start = series.iloc[-1 - trading_days]
    end = series.iloc[-1]
    if pd.isna(start) or start <= 0:
        return None
    return round(((end / start) - 1) * 100, 2)


def calc_rsi_14(series):
    if series is None or len(series) < 15:
        return None
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    latest = rs.iloc[-1]
    if pd.isna(latest):
        return None
    return round(float(100 - (100 / (1 + latest))), 1)


def calc_downside_capture(asset_close, bench_close):
    """Computes 1Y Downside Capture Ratio (%) relative to Nifty 50."""
    if asset_close is None or bench_close is None:
        return None
    a = asset_close.copy()
    b = bench_close.copy()
    a.index = pd.to_datetime(a.index).tz_localize(None)
    b.index = pd.to_datetime(b.index).tz_localize(None)

    df = pd.concat([a.pct_change().rename("a"), b.pct_change().rename("b")], axis=1).dropna().tail(252)
    down_days = df[df["b"] < 0]
    if len(down_days) < 15 or down_days["b"].mean() == 0:
        return None
    return round(float((down_days["a"].mean() / down_days["b"].mean()) * 100), 1)


def calc_yoy_history(close, start_year=1995):
    if close is None or close.empty:
        return {}
    s = close.copy()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    s = s.sort_index()

    years = [y for y in sorted(s.index.year.unique()) if y >= start_year]
    yoy = {}

    for idx, yr in enumerate(years):
        yr_slice = s[s.index.year == yr]
        if yr_slice.empty:
            continue
        end_val = float(yr_slice.iloc[-1])

        prev_slice = s[s.index.year == (yr - 1)]
        if not prev_slice.empty:
            start_val = float(prev_slice.iloc[-1])
        elif idx == 0 and len(yr_slice) > 1:
            start_val = float(yr_slice.iloc[0])
        else:
            continue

        if start_val > 0:
            yoy[str(yr)] = round(((end_val / start_val) - 1) * 100, 2)

    return yoy


def get_currency_symbol(name, ticker):
    if "VIX" in name.upper():
        return ""
    if "Yield" in name or "TNX" in ticker:
        return "%"
    if "INR" in name or ticker.endswith(".NS") or ticker.endswith(".BO"):
        return "₹"
    if "USD" in name or "Crude" in name or ticker in ["GC=F", "SI=F", "BZ=F", "EEM"]:
        return "$"
    return ""


def fetch_valuation_details(ticker):
    """Fetches trailing P/E, P/B, and Dividend Yield (%) from ticker or ETF proxy."""
    for sym in [ticker] + VALUATION_PROXIES.get(ticker, []):
        try:
            info = yf.Ticker(sym).info or {}
            pe = info.get("trailingPE")
            pb = info.get("priceToBook")
            dy = info.get("dividendYield") or info.get("trailingAnnualDividendYield")
            if pe or pb or dy:
                return (
                    round(float(pe), 2) if pe and float(pe) > 0 else None,
                    round(float(pb), 2) if pb and float(pb) > 0 else None,
                    round(float(dy) * 100, 2) if dy and 0 < float(dy) < 0.25 else (round(float(dy), 2) if dy and float(dy) >= 0.25 else None),
                )
        except Exception:
            continue
    return None, None, None


HISTORY_PATH = "data/history.jsonl"


def load_history():
    rows = []
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
    return rows


def fpi_streak_from_history(history, today_fpi, today_key):
    """Consecutive net-sell sessions ending today, from real stored flows (one row per session date)."""
    if today_fpi >= 0:
        return 0
    streak = 1
    for row in reversed([h for h in history if h.get("flow_date") != today_key]):
        v = (row.get("flows") or {}).get("fpi_net_cr")
        if v is not None and v < 0:
            streak += 1
        else:
            break
    return streak


def append_history(snapshot):
    """One row per flow/session date; the last run of the day overwrites that day's row."""
    prices, pes = {}, {}
    for cat, items in snapshot.get("markets", {}).items():
        for x in items:
            prices[x["name"]] = x.get("price")
            if x.get("pe") is not None:
                pes[x["name"]] = x["pe"]
    fl = snapshot.get("institutional_flows", {})
    key = fl.get("as_of_date") or datetime.now(IST).strftime("%d-%b-%Y")
    row = {
        "ts": snapshot.get("updated_at_ist"),
        "flow_date": key,
        "flows": {"fpi_net_cr": fl.get("fpi_net_cr"), "dii_net_cr": fl.get("dii_net_cr"), "source": fl.get("source")},
        "prices": prices,
        "pe": pes,
    }
    hist = [h for h in load_history() if h.get("flow_date") != key]
    hist.append(row)
    hist = hist[-800:]
    os.makedirs("data", exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        for h in hist:
            f.write(json.dumps(h) + "\n")


def fetch_fpi_dii_flows(macro_cfg):
    """Attempts live NSE FII/DII daily cash flow scrape with config.yaml fallback."""
    fpi_net = float(macro_cfg.get("fpi_net_cr", -1850.0))
    dii_net = float(macro_cfg.get("dii_net_cr", 2410.0))
    sell_streak = None
    source_tag = "MANUAL fallback (config.yaml)"
    as_of_date = datetime.now(IST).strftime("%d-%b-%Y")

    try:
        sess = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nseindia.com/reports/fii-dii",
        }
        sess.get("https://www.nseindia.com", headers=headers, timeout=8)
        r = sess.get("https://www.nseindia.com/api/fiidiiTradeReact", headers=headers, timeout=10)
        if r.status_code == 200:
            rows = r.json()
            for row in rows:
                cat = str(row.get("category", "")).upper()
                val = float(str(row.get("netValue", "0")).replace(",", ""))
                if "FII" in cat or "FPI" in cat:
                    fpi_net = round(val, 2)
                    as_of_date = row.get("date", as_of_date)
                elif "DII" in cat:
                    dii_net = round(val, 2)
            source_tag = "LIVE: NSE cash market"
    except Exception as e:
        print(f"NSE FPI/DII live fetch fallback ({e})")

    if sell_streak is None:
        sell_streak = fpi_streak_from_history(load_history(), fpi_net, as_of_date)
    net_institutional = round(fpi_net + dii_net, 2)
    return {
        "as_of_date": as_of_date,
        "fpi_net_cr": fpi_net,
        "dii_net_cr": dii_net,
        "net_institutional_cr": net_institutional,
        "fpi_sell_streak_days": sell_streak,
        "source": source_tag,
    }


def compute_vol_stance(price, dist_200dma, r_1d, r_1w):
    if r_1d is not None and r_1d >= 15:
        return "Sell | 1D volatility spike"
    if dist_200dma is not None and dist_200dma > 30:
        return "Sell | Elevated stress"
    if price < 14 and (r_1w is None or r_1w <= 2):
        return "Buy | Calm volatility"
    return "Hold | Normal volatility"


def compute_bi_stance(pe, dist_200dma, from_52w_high, rsi_14, r_1m, r_3m, r_1y, sharpe, vol_1y, is_equity=True):
    score = 0.0
    reasons = []

    if is_equity and pe is not None:
        if pe < 18:
            score += 1.5
            reasons.append("reasonable valuation")
        elif pe <= 24:
            score += 0.75
            reasons.append("fair valuation")
        elif pe <= 30:
            score -= 0.5
            reasons.append("rich valuation")
        else:
            score -= 1.5
            reasons.append("stretched valuation")

    if dist_200dma is not None:
        if -12 <= dist_200dma < 0 and r_1m is not None and r_1m > 0:
            score += 1.5
            reasons.append("bouncing near long-term average")
        elif 0 <= dist_200dma <= 12:
            score += 1.0
            reasons.append("healthy long-term trend")
        elif dist_200dma > 18:
            score -= 1.25
            reasons.append("far above long-term average")
        elif dist_200dma < -15:
            score -= 1.0
            reasons.append("below long-term average")

    if rsi_14 is not None:
        if rsi_14 > 75:
            score -= 0.5
            reasons.append("short-term overbought")
        elif rsi_14 < 30:
            score += 0.5
            reasons.append("short-term oversold")

    if from_52w_high is not None and from_52w_high < -20 and (r_1m is None or r_1m <= 0):
        score -= 0.75
        reasons.append("well off 1-year high")

    pos_horizons = sum(1 for x in [r_1m, r_3m, r_1y] if x is not None and x > 0)
    neg_horizons = sum(1 for x in [r_1m, r_3m, r_1y] if x is not None and x < 0)
    if pos_horizons == 3:
        score += 1.0
        reasons.append("steady multi-month gains")
    elif neg_horizons == 3:
        score -= 1.0
        reasons.append("broad multi-month weakness")

    if sharpe is not None:
        if sharpe >= 1.0:
            score += 0.75
            reasons.append("strong risk-adjusted return")
        elif sharpe < -0.25:
            score -= 0.75
            reasons.append("weak risk-adjusted return")

    if vol_1y is not None and vol_1y > 28 and is_equity:
        score -= 0.5
        reasons.append("high price swings")

    if score >= 1.25:
        label = "Buy"
    elif score >= -0.75:
        label = "Hold"
    else:
        label = "Sell"

    reasoning = ", ".join(reasons[:2]) if reasons else "mixed signals"
    return f"{label} | {reasoning}"


def analyze_series(name, ticker, close, rf_rate=0.068, pe=None, pb=None, div_yield=None, currency="", mode="equity", include_yoy=False):
    current_price = round(float(close.iloc[-1]), 2)

    r_1d = calc_pct_return(close, 1)
    r_1w = calc_pct_return(close, 5)
    r_1m = calc_pct_return(close, 21)
    r_3m = calc_pct_return(close, 63)
    r_1y = calc_pct_return(close, 252)
    r_3y_cagr = calc_ny_cagr(close, 3)
    r_5y_cagr = calc_ny_cagr(close, 5)

    recent_1y = close.tail(252)
    daily_ret = recent_1y.pct_change().dropna()
    ann_vol = round(float(daily_ret.std() * np.sqrt(252) * 100), 2) if len(daily_ret) > 10 else None
    daily_std_pct = float(daily_ret.std() * 100) if len(daily_ret) > 10 else None
    z_score_1d = round(r_1d / daily_std_pct, 2) if (r_1d is not None and daily_std_pct and daily_std_pct > 0) else None

    sharpe = None
    if r_1y is not None and ann_vol and ann_vol > 0:
        sharpe = round(((r_1y / 100) - rf_rate) / (ann_vol / 100), 2)

    rolling_max = recent_1y.cummax()
    max_dd_1y = round(float(((recent_1y / rolling_max - 1) * 100).min()), 2) if len(recent_1y) > 5 else None

    dma_200 = float(close.tail(200).mean()) if len(close) >= 200 else None
    dist_200dma = round(((current_price / dma_200) - 1) * 100, 2) if dma_200 else None

    high_52w = float(recent_1y.max())
    from_52w_high = round(((current_price / high_52w) - 1) * 100, 2) if high_52w > 0 else None

    rsi_14 = None if mode == "vol" else calc_rsi_14(close)

    if mode == "vol":
        bi_stance = compute_vol_stance(current_price, dist_200dma, r_1d, r_1w)
    else:
        bi_stance = compute_bi_stance(
            pe, dist_200dma, from_52w_high, rsi_14, r_1m, r_3m, r_1y, sharpe, ann_vol, is_equity=(mode == "equity")
        )

    out = {
        "name": name,
        "ticker": ticker,
        "currency": currency,
        "price": current_price,
        "1D": r_1d,
        "1W": r_1w,
        "1M": r_1m,
        "3M": r_3m,
        "1Y": r_1y,
        "3Y_CAGR": r_3y_cagr,
        "5Y_CAGR": r_5y_cagr,
        "volatility_1y": ann_vol,
        "z_score_1d": z_score_1d,
        "sharpe_1y": sharpe,
        "max_drawdown_1y": max_dd_1y,
        "rsi_14": rsi_14,
        "from_52w_high": from_52w_high,
        "dist_200dma": dist_200dma,
        "pe": pe if mode == "equity" else None,
        "pb": pb if mode == "equity" else None,
        "div_yield": div_yield,
        "bi_stance": bi_stance,
    }
    if include_yoy:
        out["yoy_returns"] = calc_yoy_history(close, start_year=1995)
    return out


def analyze_ticker(name, ticker, category, rf_rate=0.068, include_yoy=False):
    try:
        period = "max" if include_yoy else "6y"
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        if hist.empty or len(hist) < 10:
            return None, None

        close = hist["Close"].dropna()
        clean_name = clean_label(name)
        currency = get_currency_symbol(clean_name, ticker)

        if category == "volatility_indices":
            mode = "vol"
            pe_ratio, pb_ratio, div_yield = None, None, None
        elif category in ["indian_equity", "indian_sectors", "global_indices"]:
            mode = "equity"
            pe_ratio, pb_ratio, div_yield = fetch_valuation_details(ticker)
        elif category == "reits_invits":
            mode = "macro"
            _, _, div_yield = fetch_valuation_details(ticker)
            pe_ratio, pb_ratio = None, None
        else:
            mode = "macro"
            pe_ratio, pb_ratio, div_yield = None, None, None

        return analyze_series(
            clean_name, ticker, close, rf_rate, pe_ratio, pb_ratio, div_yield, currency, mode=mode, include_yoy=include_yoy
        ), close
    except Exception as e:
        print(f"Error fetching {name} ({ticker}): {e}")
        return None, None


def build_fund_alpha_comparison(series_cache, rf_rate=0.068):
    rows = []
    for item in EQUITY_FUND_PROXIES:
        try:
            hist = yf.Ticker(item["ticker"]).history(period="4y", auto_adjust=True)
            if hist.empty or len(hist) < 60:
                continue
            f_close = hist["Close"].dropna()
            b_close = series_cache.get(item["benchmark_ticker"])
            f_1y = calc_pct_return(f_close, 252)
            f_3y = calc_ny_cagr(f_close, 3)
            b_1y = calc_pct_return(b_close, 252) if b_close is not None else None
            b_3y = calc_ny_cagr(b_close, 3) if b_close is not None else None

            alpha_1y = round(f_1y - b_1y, 2) if (f_1y is not None and b_1y is not None) else None

            recent_1y = f_close.tail(252)
            ann_vol = round(float(recent_1y.pct_change().dropna().std() * np.sqrt(252) * 100), 2)
            sharpe = round(((f_1y / 100) - rf_rate) / (ann_vol / 100), 2) if (f_1y is not None and ann_vol > 0) else None
            max_dd = round(float(((recent_1y / recent_1y.cummax() - 1) * 100).min()), 2)
            down_cap = calc_downside_capture(f_close, b_close)

            rows.append({
                "fund": item["fund"],
                "category": item["category"],
                "fund_1y": f_1y,
                "bench_1y": b_1y,
                "alpha_vs_bench": alpha_1y,
                "fund_3y_cagr": f_3y,
                "std_dev": ann_vol,
                "sharpe": sharpe,
                "downside_capture": down_cap,
                "max_dd": max_dd,
            })
        except Exception as e:
            print(f"Fund proxy error ({item['fund']}): {e}")
    return rows


def fetch_amfi_debt_schemes(per_bucket=3):
    schemes = []
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(AMFI_NAV_URL, headers=headers, timeout=25)
        resp.raise_for_status()
        lines = resp.text.splitlines()

        found_counts = {b["bucket"]: 0 for b in AMFI_DEBT_BUCKETS}
        for line in lines:
            parts = line.split(";")
            if len(parts) < 5:
                continue
            scheme_name = parts[3].strip()
            nav_str = parts[4].strip()
            nav_date = parts[5].strip() if len(parts) > 5 else ""

            try:
                nav_val = round(float(nav_str), 4)
            except ValueError:
                continue

            lower_name = scheme_name.lower()
            if "growth" not in lower_name:
                continue

            for b in AMFI_DEBT_BUCKETS:
                b_name = b["bucket"]
                if found_counts[b_name] >= per_bucket:
                    continue
                if any(kw in lower_name for kw in b["keywords"]):
                    schemes.append({
                        "scheme_name": scheme_name[:68],
                        "bucket": b_name,
                        "duration": b["duration"],
                        "credit": b["credit"],
                        "nav": nav_val,
                        "nav_date": nav_date,
                    })
                    found_counts[b_name] += 1
                    break

            if all(cnt >= per_bucket for cnt in found_counts.values()):
                break
    except Exception as e:
        print(f"AMFI NAV fetch error: {e}")
    return schemes


def build_rules_alerts(snapshot):
    """Rule-based 'What's Interesting Today' intelligence layer."""
    alerts = []
    markets = snapshot.get("markets", {})
    macro = snapshot.get("macro_manual", {})
    flows = snapshot.get("institutional_flows", {})

    # 1. Nifty down more than 5% from its high
    nifty = next((x for x in markets.get("indian_equity", []) if "nifty 50" in x["name"].lower()), None)
    if nifty and nifty.get("from_52w_high") is not None:
        dd = nifty["from_52w_high"]
        if dd <= -5.0:
            alerts.append({
                "severity": "ALERT",
                "title": f"Nifty 50 is {abs(dd):.1f}% below its 52-week high",
                "detail": "Correction threshold (>5% off peak) breached — review staggered STP tranches into broad equity.",
            })
        else:
            alerts.append({
                "severity": "WATCH",
                "title": f"Nifty 50 within {abs(dd):.1f}% of 52-week high",
                "detail": "Market remains above the 5% pullback trigger; stick to disciplined asset allocation.",
            })

    # 2. Sector moved more than 2 standard deviations (1D)
    extreme_sectors = [
        x for x in markets.get("indian_sectors", [])
        if x.get("z_score_1d") is not None and abs(x["z_score_1d"]) >= 2.0
    ]
    if extreme_sectors:
        for s in extreme_sectors:
            alerts.append({
                "severity": "ALERT",
                "title": f"{s['name']} moved {s['1D']:+.2f}% ({s['z_score_1d']:+.1f}σ daily move)",
                "detail": "Statistically outsized single-day sector move (>2 standard deviations) — check for news catalyst.",
            })
    else:
        alerts.append({
            "severity": "OK",
            "title": "No sector breached ±2σ daily volatility",
            "detail": "All 10 Indian sectoral indices traded within normal 2-standard-deviation daily bands.",
        })

    # 3. Gold-to-Equity ratio check
    gold_inr = next((x for x in markets.get("macro_commodities_fx", []) if "gold inr" in x["name"].lower()), None)
    if nifty and gold_inr and nifty.get("price") and gold_inr.get("price"):
        ratio = round(gold_inr["price"] / nifty["price"], 2)
        if ratio >= 4.2 or ratio <= 2.4:
            alerts.append({
                "severity": "ALERT",
                "title": f"Gold-to-Nifty ratio at extreme ({ratio:.2f}x)",
                "detail": "Gold (INR/10g) vs. Nifty 50 ratio is at a historical extreme — consider multi-asset rebalancing.",
            })
        else:
            alerts.append({
                "severity": "WATCH",
                "title": f"Gold-to-Nifty ratio at {ratio:.2f}x (Normal Band)",
                "detail": "Gold vs. Nifty relative pricing sits inside balanced multi-asset ranges.",
            })

    # 4. FPI selling lasted more than 5 sessions
    streak = flows.get("fpi_sell_streak_days", 0)
    if streak > 5:
        alerts.append({
            "severity": "ALERT",
            "title": f"FPI net selling streak at {streak} consecutive sessions",
            "detail": "Sustained foreign outflows (>5 sessions) — watch large-cap liquidity and DII absorption.",
        })
    else:
        alerts.append({
            "severity": "WATCH",
            "title": f"FPI cash flow streak: {streak} sell session(s) (Latest: ₹{flows.get('fpi_net_cr', 0):+,.0f} Cr)",
            "detail": f"DII flow at ₹{flows.get('dii_net_cr', 0):+,.0f} Cr cushioning domestic equities.",
        })

    # 6. Yield curve sharp move check
    gsec_now = float(macro.get("india_10y_gsec_approx", 6.85))
    gsec_prev = float(macro.get("india_10y_gsec_prev_week", 6.78))
    bps_move = round((gsec_now - gsec_prev) * 100)
    if abs(bps_move) >= 15:
        alerts.append({
            "severity": "ALERT",
            "title": f"India 10Y G-Sec yield shifted {bps_move:+d} bps",
            "detail": "Sharp sovereign yield move — reassess Gilt/Long Duration vs. Short Duration allocation.",
        })
    else:
        alerts.append({
            "severity": "OK",
            "title": f"India 10Y G-Sec steady ({gsec_now:.2f}%, {bps_move:+d} bps WoW)",
            "detail": "Sovereign yield curve movement remains contained (<15 bps threshold).",
        })

    return alerts


def fetch_rss_news(rss_config, max_per_feed=6):
    news_pool = {"india": [], "global": [], "regulatory": []}
    for region in ["india", "global", "regulatory"]:
        for source in rss_config.get(region, []):
            try:
                feed = feedparser.parse(source["url"])
                for entry in feed.entries[:max_per_feed]:
                    news_pool[region].append({
                        "source": source["name"],
                        "title": entry.get("title", "").strip(),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "region": region.upper(),
                    })
            except Exception as e:
                print(f"RSS error ({source['name']}): {e}")
    return news_pool


def run_fetch():
    cfg = load_config()
    macro_cfg = cfg.get("macro_manual", {})
    rf_rate = macro_cfg.get("risk_free_rate_india", 0.068)

    snapshot = {
        "updated_at_ist": datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST"),
        "macro_manual": macro_cfg,
        "amfi_monthly_manual": cfg.get("amfi_monthly_manual", {}),
        "nfo_watchlist": cfg.get("nfo_watchlist", []),
        "institutional_flows": fetch_fpi_dii_flows(macro_cfg),
        "markets": {},
        "fund_alpha": [],
        "amfi_debt_schemes": [],
        "raw_news": {},
        "verified_news": [],
        "ai_strategist": {},
        "whats_interesting": [],
    }

    series_cache = {}
    for category, tickers in cfg["benchmarks"].items():
        snapshot["markets"][category] = []
        track_yoy = category in ["indian_equity", "global_indices"]
        for name, ticker in tickers.items():
            print(f"Fetching {name} ({ticker})...")
            data, close = analyze_ticker(name, ticker, category, rf_rate, include_yoy=track_yoy)
            if data:
                snapshot["markets"][category].append(data)
                series_cache[ticker] = close

    # Add Downside Capture vs Nifty 50 on Indian Equity & Sectors
    nifty_close = series_cache.get("^NSEI")
    for cat in ["indian_equity", "indian_sectors"]:
        for row in snapshot["markets"].get(cat, []):
            row["downside_capture"] = calc_downside_capture(series_cache.get(row["ticker"]), nifty_close)

    # Add Talking Points on Indian Sectors
    for row in snapshot["markets"].get("indian_sectors", []):
        tp = SECTOR_TALKING_POINTS.get(row["name"], ("Positive relative momentum vs. Nifty.", "Underperforming Nifty on near-term rotation."))
        r3m = row.get("3M") or 0
        row["talking_point"] = tp[0] if r3m >= 0 else tp[1]

    if "GC=F" in series_cache and "INR=X" in series_cache:
        gold_usd = series_cache["GC=F"].tz_localize(None)
        usdinr = series_cache["INR=X"].tz_localize(None)
        aligned = pd.concat([gold_usd.rename("gold"), usdinr.rename("fx")], axis=1).ffill().dropna()
        if len(aligned) > 20:
            gold_inr_10g = (aligned["gold"] / 31.1034768) * aligned["fx"] * 10
            gold_inr_data = analyze_series(
                "Gold INR / 10g", "GOLD_INR_10G", gold_inr_10g, rf_rate, currency="₹", mode="macro"
            )
            snapshot["markets"].setdefault("macro_commodities_fx", []).insert(0, gold_inr_data)

    print("Building Equity Fund vs Benchmark & Category Median Alpha...")
    snapshot["fund_alpha"] = build_fund_alpha_comparison(series_cache, rf_rate=rf_rate)

    print("Fetching live Indian Debt & Liquid MF NAVs from AMFI...")
    snapshot["amfi_debt_schemes"] = fetch_amfi_debt_schemes(per_bucket=3)

    snapshot["raw_news"] = fetch_rss_news(cfg["rss_feeds"])
    snapshot["whats_interesting"] = build_rules_alerts(snapshot)

    expected = sum(len(v) for v in cfg["benchmarks"].values())
    fetched = sum(len(v) for v in snapshot["markets"].values() if isinstance(v, list))
    snapshot["data_health"] = {
        "tickers_expected": expected,
        "tickers_fetched": min(fetched, expected),
        "amfi_nav_rows": len(snapshot["amfi_debt_schemes"]),
        "news_items": sum(len(v) for v in snapshot["raw_news"].values()),
        "flows_source": snapshot["institutional_flows"].get("source"),
        "manual_data_asof": macro_cfg.get("manual_data_asof", "unverified"),
    }
    append_history(snapshot)

    os.makedirs("data", exist_ok=True)
    with open("data/market_snapshot.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    print("Saved data/market_snapshot.json successfully.")
    return snapshot


if __name__ == "__main__":
    run_fetch()
