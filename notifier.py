import os
import json
import html
import smtplib
import urllib.parse
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


DISCLAIMER = (
    "For information and education only. Not investment advice or a recommendation. "
    "Mutual fund investments are subject to market risks; read all scheme-related documents carefully. "
    "Past performance may or may not be sustained in the future."
)
STANCE_LABELS = {"Buy": "Favourable", "Hold": "Neutral", "Sell": "Cautious"}


def e(x):
    return html.escape(str(x if x is not None else ""))


def safe_url(u):
    u = str(u or "")
    return u if u.startswith(("http://", "https://")) else "#"


def neutral_stance(text):
    head, _, reason = str(text or "Hold | mixed signals").partition(" | ")
    label = STANCE_LABELS.get(head.strip().split(" ")[0].title(), head.strip())
    return f"{label} | {reason}" if reason else label


def fmt_pct(val):
    if val is None:
        return "—"
    color = "#137333" if val >= 0 else "#c5221f"
    sign = "+" if val > 0 else ""
    return f'<span style="color:{color};font-weight:600;">{sign}{val:.2f}%</span>'


def build_html_email(snapshot, dashboard_url):
    updated = snapshot.get("updated_at_ist", "")
    ai = snapshot.get("ai_strategist", {})
    news = snapshot.get("verified_news", [])

    # Build key rows for Indian Equity + Sectors + Global
    rows_html = ""
    for cat_key, cat_label in [
        ("indian_equity", "Indian Broad Market"),
        ("indian_sectors", "Indian Sectors"),
        ("global_indices", "Global Exposure"),
        ("macro_commodities_fx", "Macro, FX & Commodities"),
    ]:
        items = snapshot.get("markets", {}).get(cat_key, [])
        if not items:
            continue
        rows_html += f"""
        <tr style="background:#f1f3f4;">
          <td colspan="6" style="padding:8px 10px;font-weight:700;color:#1a202c;font-size:12px;text-transform:uppercase;">{e(cat_label)}</td>
        </tr>
        """
        for x in items:
            rows_html += f"""
            <tr style="border-bottom:1px solid #e2e8f0;">
              <td style="padding:7px 10px;font-weight:600;color:#111827;">{e(x['name'])}</td>
              <td style="padding:7px 8px;text-align:right;">{e(x['price'])}</td>
              <td style="padding:7px 8px;text-align:right;">{fmt_pct(x.get('1D'))}</td>
              <td style="padding:7px 8px;text-align:right;">{fmt_pct(x.get('1M'))}</td>
              <td style="padding:7px 8px;text-align:right;">{fmt_pct(x.get('1Y'))}</td>
              <td style="padding:7px 8px;font-size:12px;color:#374151;">{e(neutral_stance(x.get('bi_stance')))}</td>
            </tr>
            """

    opp_html = "".join(f"<li style='margin-bottom:4px;'>{e(o)}</li>" for o in ai.get("opportunities", []))
    risk_html = "".join(f"<li style='margin-bottom:4px;'>{e(r)}</li>" for r in ai.get("risk_flags", []))

    news_html = ""
    for n in news:
        news_html += f"""
        <li style="margin-bottom:10px;">
          <span style="background:#1e293b;color:#f8fafc;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:600;">{e(n.get('region',''))} • {e(n.get('tag',''))}</span>
          <a href="{e(safe_url(n.get('link')))}" style="color:#0f172a;font-weight:600;text-decoration:none;"> {e(n.get('title',''))}</a>
          <div style="font-size:12px;color:#475569;margin-top:2px;">{e(n.get('impact',''))} <em>({e(n.get('source',''))})</em></div>
        </li>
        """

    return f"""
    <html>
      <body style="font-family:Arial,Helvetica,sans-serif;background:#f8fafc;padding:20px;color:#0f172a;">
        <div style="max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
          <div style="background:#0b0f17;color:#d4af37;padding:20px 24px;">
            <h2 style="margin:0;font-size:20px;letter-spacing:0.5px;">WEALTH MANAGEMENT DAILY BRIEF</h2>
            <p style="margin:4px 0 0 0;color:#cbd5e1;font-size:12px;">{updated} &nbsp;|&nbsp; Regime: <strong>{e(ai.get('market_regime', 'N/A'))}</strong></p>
          </div>

          <div style="padding:20px 24px;">
            <h3 style="margin-top:0;color:#0f172a;border-bottom:2px solid #d4af37;padding-bottom:6px;">AI Strategist Desk</h3>
            <p style="font-size:13px;margin:8px 0;"><strong>Opportunities:</strong></p>
            <ul style="font-size:13px;padding-left:18px;margin-top:4px;">{opp_html}</ul>
            <p style="font-size:13px;margin:8px 0;"><strong>Risk & Stance Flags:</strong></p>
            <ul style="font-size:13px;padding-left:18px;margin-top:4px;">{risk_html}</ul>
            <p style="font-size:13px;background:#f8fafc;padding:10px;border-left:3px solid #0f172a;"><strong>Debt & Macro:</strong> {e(ai.get('debt_and_macro', 'N/A'))}</p>

            <h3 style="color:#0f172a;border-bottom:2px solid #d4af37;padding-bottom:6px;margin-top:24px;">Market & Sector Pulse</h3>
            <table style="width:100%;border-collapse:collapse;font-size:12px;">
              <thead>
                <tr style="background:#0f172a;color:#ffffff;">
                  <th style="padding:8px 10px;text-align:left;">Benchmark</th>
                  <th style="padding:8px;text-align:right;">Price</th>
                  <th style="padding:8px;text-align:right;">1D</th>
                  <th style="padding:8px;text-align:right;">1M</th>
                  <th style="padding:8px;text-align:right;">1Y</th>
                  <th style="padding:8px;text-align:left;">Signal</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>

            <h3 style="color:#0f172a;border-bottom:2px solid #d4af37;padding-bottom:6px;margin-top:24px;">Top 10 Verified Financial News </h3>
            <ul style="list-style:none;padding-left:0;font-size:13px;">{news_html}</ul>

            <p style="font-size:11px;color:#64748b;margin-top:20px;border-top:1px solid #e2e8f0;padding-top:10px;">{DISCLAIMER}</p>
            <div style="text-align:center;margin-top:24px;">
              <a href="{e(safe_url(dashboard_url))}" style="background:#0b0f17;color:#d4af37;padding:12px 24px;text-decoration:none;border-radius:5px;font-weight:700;font-size:13px;">Open Live Dashboard →</a>
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def send_email(snapshot, dashboard_url):
    sender = os.environ.get("GMAIL_ADDRESS")
    app_pwd = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("RECIPIENT_EMAIL", sender)

    if not sender or not app_pwd:
        print("Email credentials not set. Skipping email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Wealth Daily Brief — {snapshot.get('updated_at_ist', '')}"
    msg["From"] = sender
    msg["To"] = recipient

    html_body = build_html_email(snapshot, dashboard_url)
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_pwd)
        server.sendmail(sender, recipient, msg.as_string())
    print("HTML Email digest sent successfully.")


def send_whatsapp(snapshot, dashboard_url):
    phone = os.environ.get("WHATSAPP_PHONE")
    apikey = os.environ.get("CALLMEBOT_API_KEY")

    if not phone or not apikey:
        print("WhatsApp credentials not set. Skipping WhatsApp.")
        return

    ai = snapshot.get("ai_strategist", {})
    eq = snapshot.get("markets", {}).get("indian_equity", [])
    nifty = next((x for x in eq if "Nifty 50" in x["name"]), None)
    vix = next((x for x in snapshot.get("markets", {}).get("volatility_indices", []) if "India VIX" in x["name"]), None)

    lines = [
        f"*WEALTH DAILY BRIEF* ({snapshot.get('updated_at_ist', '')})",
        f"Regime: _{ai.get('market_regime', 'N/A')}_",
        "",
    ]
    if nifty:
        lines.append(f"• Nifty 50: {nifty['price']} ({nifty.get('1D', 0):+}% 1D | {nifty.get('1M', 0):+}% 1M)")
    if vix:
        lines.append(f"• India VIX: {vix['price']} ({vix.get('1D', 0):+}%)")

    lines.append("\n*Top Opportunities:*")
    for o in ai.get("opportunities", [])[:2]:
        lines.append(f"- {o}")

    lines.append("\n*Top 4 Headlines:*")
    for n in snapshot.get("verified_news", [])[:4]:
        lines.append(f"• [{n.get('region','')}] {n.get('title','')}")

    lines.append(f"\nLive Dashboard: {dashboard_url}")
    lines.append("\n_Information only, not investment advice. Mutual fund investments are subject to market risks._")
    text = "\n".join(lines)

    url = (
        f"https://api.callmebot.com/whatsapp.php?phone={phone}"
        f"&text={urllib.parse.quote(text)}&apikey={apikey}"
    )
    resp = requests.get(url, timeout=15)
    print(f"WhatsApp status: {resp.status_code}")


def run_notifier():
    snapshot_path = "data/market_snapshot.json"
    if not os.path.exists(snapshot_path):
        print("No snapshot found.")
        return

    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)

    dashboard_url = os.environ.get("DASHBOARD_URL", "https://share.streamlit.io")
    send_email(snapshot, dashboard_url)
    send_whatsapp(snapshot, dashboard_url)


if __name__ == "__main__":
    run_notifier()
