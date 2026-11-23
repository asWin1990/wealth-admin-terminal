import os
import json
from google import genai
from google.genai import types


def build_fallback_output(snapshot):
    """Populates 10 news items (4 India / 6 Global) and a deterministic BI brief if Gemini is unavailable."""
    raw = snapshot.get("raw_news", {})
    india_items = raw.get("india", [])[:4]
    global_items = raw.get("global", [])[:6]

    verified = []
    for n in india_items:
        verified.append({
            "region": "INDIA",
            "source": n.get("source", "Tier-1 India"),
            "title": n.get("title", ""),
            "link": n.get("link", ""),
            "tag": "India Markets",
            "impact": "Monitor for domestic equity flows, sector rotation, and RBI/rate sensitivity.",
        })
    for n in global_items:
        verified.append({
            "region": "GLOBAL",
            "source": n.get("source", "Tier-1 Global"),
            "title": n.get("title", ""),
            "link": n.get("link", ""),
            "tag": "Global Macro",
            "impact": "Relevant for international FoF allocation, USD/INR, commodities, and global yields.",
        })

    all_eq = snapshot.get("markets", {}).get("indian_equity", []) + snapshot.get("markets", {}).get("indian_sectors", [])
    strong = [x["name"] for x in all_eq if "Strong Buy" in x.get("bi_stance", "") or "Accumulate" in x.get("bi_stance", "")][:3]
    cautious = [x["name"] for x in all_eq if "Avoid" in x.get("bi_stance", "") or "Cautious" in x.get("bi_stance", "")][:2]

    macro = snapshot.get("macro_manual", {})
    repo = macro.get("rbi_repo_rate", 6.50)
    gsec = macro.get("india_10y_gsec_approx", 6.85)
    spread = round(gsec - repo, 2)

    return {
        "verified_news": verified,
        "ai_strategist": {
            "market_regime": "Data-Driven Multi-Asset Regime",
            "opportunities": [
                f"Constructive BI Stance buckets: {', '.join(strong)}." if strong else "Review P/E vs. 200-DMA pullbacks across large and flexi-cap benchmarks.",
                "Compare 3M/1Y momentum against 52W High discounts before adding cyclical exposure.",
            ],
            "risk_flags": [
                f"Cautious / Watch buckets: {', '.join(cautious)}." if cautious else "Watch volatility spikes and overextended distance above 200-DMA.",
                "Avoid chasing single-day moves without multi-horizon (1M/3M) confirmation.",
            ],
            "debt_and_macro": (
                f"RBI Repo is at {repo:.2f}% vs. ~{gsec:.2f}% 10Y G-Sec (spread: +{spread:.2f}%). "
                "Pair liquid/short-duration funds for stability with calibrated duration exposure where yield spreads compensate for rate volatility."
            ),
        },
    }


def sanitize_news(items, raw_news):
    """Keep only items whose link exists in the fetched RSS pool (blocks hallucinated URLs)."""
    allowed = {n.get("link") for lst in raw_news.values() for n in lst if n.get("link")}
    return [n for n in items if n.get("link") in allowed]


def run_ai_analysis():
    snapshot_path = "data/market_snapshot.json"
    if not os.path.exists(snapshot_path):
        print("Snapshot not found. Run fetch_data.py first.")
        return

    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set. Using fallback news & BI summary.")
        fb = build_fallback_output(snapshot)
        snapshot["verified_news"] = fb["verified_news"]
        snapshot["ai_strategist"] = fb["ai_strategist"]
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        return

    client = genai.Client(api_key=api_key)

    market_summary = {}
    for cat, items in snapshot.get("markets", {}).items():
        market_summary[cat] = [
            {
                "name": x["name"],
                "1D": x.get("1D"),
                "1M": x.get("1M"),
                "3M": x.get("3M"),
                "1Y": x.get("1Y"),
                "dist_200dma": x.get("dist_200dma"),
                "from_52w_high": x.get("from_52w_high"),
                "vol_1y": x.get("volatility_1y"),
                "sharpe": x.get("sharpe_1y"),
                "pe": x.get("pe"),
                "bi_stance": x.get("bi_stance", "Neutral"),
            }
            for x in items
        ]

    raw_news = snapshot.get("raw_news", {})

    prompt = f"""
You are a Senior Wealth Management Strategist advising an Indian Mutual Fund & Multi-Asset advisor.
Analyze today's market data, debt/macro rates, and raw Tier-1 RSS news below.

MARKET DATA:
{json.dumps(market_summary)}

DEBT & LIQUID MF NAVs (AMFI):
{json.dumps(snapshot.get("amfi_debt_schemes", []))}

MACRO RATES:
{json.dumps(snapshot.get("macro_manual", {}))}

RAW NEWS POOL:
{json.dumps(raw_news)}

Return ONLY valid JSON with this exact structure:
{{
  "verified_news": [
    {{
      "region": "INDIA" or "GLOBAL",
      "source": "Source Name",
      "title": "Clean, factual headline (no clickbait)",
      "link": "exact URL from raw news",
      "tag": "e.g., India Equity | Global Macro | Debt/Duration | Commodities | Sectoral",
      "impact": "1-sentence takeaway for a wealth advisor"
    }}
  ],
  "ai_strategist": {{
    "market_regime": "1 short phrase",
    "opportunities": ["2-3 specific bullets"],
    "risk_flags": ["2 bullets"],
    "debt_and_macro": "2 sentences on RBI Repo, yields, duration positioning, and macro."
  }}
}}

STRICT RULES:
1. Select up to 10 news items (aim for 4 INDIA and 6 GLOBAL from RAW NEWS POOL).
2. Only use links and facts present in RAW NEWS POOL.
3. Educational, neutral tone for an AMFI-registered distributor: describe conditions and risks. Do NOT tell anyone to buy, sell or switch a specific security, and do not predict returns.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        result = json.loads(response.text)
        v_news = sanitize_news(result.get("verified_news", []), raw_news)
        ai_brief = result.get("ai_strategist", {})

        if not v_news or not ai_brief:
            fb = build_fallback_output(snapshot)
            snapshot["verified_news"] = v_news or fb["verified_news"]
            snapshot["ai_strategist"] = ai_brief or fb["ai_strategist"]
        else:
            snapshot["verified_news"] = v_news
            snapshot["ai_strategist"] = ai_brief

        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        print("AI analysis & news headlines saved to market_snapshot.json.")
    except Exception as e:
        print(f"AI analysis error ({e}). Using fallback.")
        fb = build_fallback_output(snapshot)
        snapshot["verified_news"] = fb["verified_news"]
        snapshot["ai_strategist"] = fb["ai_strategist"]
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)


if __name__ == "__main__":
    run_ai_analysis()
