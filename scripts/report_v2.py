#!/usr/bin/env python
# report_v2.py — jewelry-style trade report built on the finance ETL database.
#
# Pipeline:
#   1. fundamentals from finreports SQL (income/balance/cash-flow/growth) — no live FMP
#   2. price bars via trading_app MarketDataClient (yfinance) -> double Bollinger + LR forecast
#   3. per-card AI commentary (OpenRouter, env-only key)
#   4. SUMMARY call: every report name + figures + its AI commentary -> one
#      conservative recommendation (HOLD / KEEP / SELL) with trader-principle
#      justification, anchored at the top of the report
#   5. single-file HTML in the D:/AI/Dashboards jewelry style (dark panels,
#      plain figure cards + AI commentary per card, ECharts candlestick)
#
# Usage: python scripts/report_v2.py --symbol AMZN [--db finreports] [--out DIR]
import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # trade report/
sys.path.insert(0, str(ROOT / "trading_app"))
sys.path.insert(0, "D:/AI/Code/finance_reports_sql_sync/scripts")

import requests

FIN_DB_DEFAULT = "finreports"
ECHARTS_MIN = Path("D:/AI/Dashboards/echarts.min.js")
OUT_DIR = ROOT / "reports" / "v2"
AI_MODEL = "gemma-4-31b-it"


# ---------------------------------------------------------------- AI backend
def _load_env_files():
    import os
    for p in (ROOT / ".env", Path("C:/Users/jess/AppData/Local/hermes/.env")):
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def ai_complete(prompt: str, max_tokens: int = 700) -> str:
    import os
    _load_env_files()
    key = os.getenv("OPENROUTER_API_KEY", "")
    if key:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": AI_MODEL, "temperature": 0.2, "max_tokens": max_tokens,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=120)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except requests.HTTPError as e:
            print(f"  (openrouter unavailable: {e} — falling back to local LM)")
    base = os.getenv("LM_BASE_URL", "http://10.0.0.201:8080").rstrip("/")
    if base.endswith(":1234"):  # LM Studio default — not running here; Strata is :8080
        base = base[:-4] + "8080"
    r = requests.post(
        f"{base}/v1/chat/completions",
        json={"model": "default", "temperature": 0.2, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=300)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    text = msg.get("content") or msg.get("reasoning_content") or ""
    return text.strip()


def ai_json(prompt: str, retries: int = 2):
    import re
    for attempt in range(retries + 1):
        text = ai_complete(prompt, max_tokens=2500)
        # scan every balanced {...} block, prefer the last one that parses
        for m in reversed(list(re.finditer(r"\{", text))):
            depth, end = 0, -1
            for i in range(m.start(), len(text)):
                if text[i] == "{": depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0: end = i; break
            if end > 0:
                try:
                    obj = json.loads(text[m.start():end + 1])
                    if isinstance(obj, dict) and ("commentary" in obj or "recommendation" in obj):
                        return obj
                except json.JSONDecodeError:
                    continue
        prompt = prompt + "\n\nPREVIOUS REPLY WAS NOT VALID JSON. Reply with pure JSON only."
    raise RuntimeError("AI did not return valid JSON after retries")


# ------------------------------------------------------- fundamentals (SQL)
def load_fundamentals(cur, symbol: str) -> dict:
    def rows(table):
        cur.execute(f"SELECT * FROM dbo.{table} WHERE symbol=? ORDER BY [date] DESC", (symbol,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    return {t: rows(t) for t in (
        "income_statement", "balance_sheet_statement", "cash_flow_statement",
        "financial_growth", "income_statement_growth",
        "balance_sheet_statement_growth", "cash_flow_statement_growth")}


def _f(v):
    return float(v) if v is not None else 0.0


def build_cards(f: dict) -> list:
    """Plain figure cards: label/value pairs computed deterministically."""
    inc, bal, cf = f["income_statement"][0], f["balance_sheet_statement"][0], f["cash_flow_statement"][0]
    g, ig = f["financial_growth"][0], f["income_statement_growth"][0]
    cards = []

    def money(v):
        a = abs(v)
        if a >= 1e12: return f"${v/1e12:.2f}T"
        if a >= 1e9:  return f"${v/1e9:.2f}B"
        if a >= 1e6:  return f"${v/1e6:.1f}M"
        return f"${v:,.0f}"

    def pct(v):
        return f"{v*100:.1f}%" if v is not None else "n/a"

    rev, ni = _f(inc["revenue"]), _f(inc["netIncome"])
    gp, oi = _f(inc["grossProfit"]), _f(inc["operatingIncome"])
    cards.append({
        "name": "Income Statement", "period": str(inc["date"]),
        "figures": [
            ("Revenue", money(rev)), ("Gross profit", money(gp)),
            ("Operating income", money(oi)), ("Net income", money(ni)),
            ("Net margin", pct(ni / rev if rev else None)),
            ("EPS diluted", f"{_f(inc['epsDiluted']):.2f}"),
        ],
        "series": [{"date": str(r["date"]), "revenue": _f(r["revenue"]), "netIncome": _f(r["netIncome"])}
                   for r in f["income_statement"]][::-1],
    })

    ta, tl = _f(bal["totalAssets"]), _f(bal["totalLiabilities"])
    cash = _f(bal["cashAndCashEquivalents"])
    debt = _f(bal.get("totalDebt")) if "totalDebt" in bal else _f(bal.get("shortTermDebt")) + _f(bal.get("longTermDebt"))
    ca, cl = _f(bal["totalCurrentAssets"]), _f(bal["totalCurrentLiabilities"])
    cards.append({
        "name": "Balance Sheet", "period": str(bal["date"]),
        "figures": [
            ("Total assets", money(ta)), ("Total liabilities", money(tl)),
            ("Cash", money(cash)), ("Total debt", money(debt)),
            ("Net debt", money(debt - cash)),
            ("Debt/assets", pct(debt / ta if ta else None)),
            ("Current ratio", f"{ca/cl:.2f}x" if cl else "n/a"),
        ],
    })

    ocf = _f(cf["operatingCashFlow"])
    capex = _f(cf.get("capitalExpenditure")) if "capitalExpenditure" in cf else 0.0
    fcf = _f(cf["freeCashFlow"]) if "freeCashFlow" in cf else ocf + capex
    cards.append({
        "name": "Cash Flow", "period": str(cf["date"]),
        "figures": [
            ("Operating cash flow", money(ocf)), ("Capex", money(capex)),
            ("Free cash flow", money(fcf)),
            ("FCF margin", pct(fcf / rev if rev else None)),
            ("FCF / net income", f"{fcf/ni:.2f}x" if ni else "n/a"),
        ],
    })

    bg = f["balance_sheet_statement_growth"][0]
    cards.append({
        "name": "Growth", "period": str(g["date"]),
        "figures": [
            ("Revenue growth", pct(_f(g["revenueGrowth"]))),
            ("Net income growth", pct(_f(g["netIncomeGrowth"]))),
            ("EPS growth", pct(_f(g["epsgrowth"]))),
            ("Asset growth", pct(_f(g["assetGrowth"]))),
            ("FCF growth", pct(_f(g["freeCashFlowGrowth"]))),
        ],
    })
    return cards


# ------------------------------------------------- technical (bars + double BB)
def build_technical(symbol: str) -> dict:
    from api.market_data_client import MarketDataClient
    df = MarketDataClient().get_bars(symbol, "1d", 120)
    close = [float(x) for x in df["close"]]
    n = len(close)

    def sma(vals, w, i):
        lo = max(0, i - w + 1)
        seg = vals[lo:i + 1]
        m = sum(seg) / len(seg)
        var = sum((x - m) ** 2 for x in seg) / len(seg)
        return m, math.sqrt(var)

    bars, bb_lines = [], {"u1": [], "l1": [], "u2": [], "l2": []}
    for i in range(n):
        m1, s1 = sma(close, 20, i)
        m2, s2 = sma(close, 20, i)
        bb_lines["u1"].append(round(m1 + 2 * s1, 2)); bb_lines["l1"].append(round(m1 - 2 * s1, 2))
        bb_lines["u2"].append(round(m1 + 3 * s2, 2)); bb_lines["l2"].append(round(m1 - 3 * s2, 2))
        r = df.iloc[i]
        bars.append({"t": str(r["timestamp"]), "o": round(float(r["open"]), 2),
                     "h": round(float(r["high"]), 2), "l": round(float(r["low"]), 2),
                     "c": round(float(r["close"]), 2)})

    # linear-regression 7-day forecast on last 60 closes
    seg = close[-60:] if n >= 60 else close
    k = len(seg); xs = list(range(k)); xm = sum(xs) / k; ym = sum(seg) / k
    num = sum((x - xm) * (y - ym) for x, y in zip(xs, seg))
    den = sum((x - xm) ** 2 for x in xs)
    slope = num / den if den else 0.0
    forecast = ym + slope * (k - 1 + 7)
    last = close[-1]
    slope_pct = slope / ym * 100 if ym else 0.0

    pos_in_band = None
    u, l = bb_lines["u1"][-1], bb_lines["l1"][-1]
    if u > l:
        pos_in_band = (last - l) / (u - l)

    return {
        "name": "Technical (Double Bollinger, 1d)", "period": f"{n} bars to {bars[-1]['t']}",
        "bars": bars, "bb": bb_lines,
        "figures": [
            ("Last close", f"${last:.2f}"),
            ("BB upper / lower", f"${u:.2f} / ${l:.2f}"),
            ("Position in band", f"{pos_in_band*100:.0f}%" if pos_in_band is not None else "n/a"),
            ("LR slope", f"{slope_pct:+.2f}%/day"),
            ("7-day LR forecast", f"${forecast:.2f}"),
        ],
        "forecast": round(forecast, 2), "last": last,
        "pos_in_band": round(pos_in_band, 3) if pos_in_band is not None else None,
    }


# ------------------------------------------------------------- AI commentary
CARD_PROMPT = """You are a conservative equity analyst writing commentary for ONE card of a
ticker report. Use ONLY the figures given. 2-4 sentences, plain language, no hype,
no price targets. Note what looks healthy, what looks risky, and what is unclear.
If a figure is n/a, say data is missing rather than guessing.

TICKER: {symbol}
CARD: {card_name} (period {period})
FIGURES:
{figures}
{series}
Return ONLY this JSON: {{"commentary": "..."}}"""

SUMMARY_PROMPT = """You are a risk-first trading desk lead. Below are ALL report cards for
{symbol}: each card's name, its figures, and the per-card analyst commentary.

{bundle}

Decide ONE conservative recommendation for a current holder of {symbol}:
- "hold"  — keep the position, no additions, no exits; thesis intact but not compelling enough to add
- "keep"  — actively continue/add with a defined plan; evidence is clearly favorable
- "sell"  — reduce or exit; evidence of deterioration or overvaluation outweighs the thesis

Guiding principles you MUST apply and cite in the justification:
1. Capital preservation first; conviction must be proportional to evidence.
2. Do not chase momentum; a stretched position in the Bollinger band is a caution flag, not a buy signal.
3. Deteriorating fundamentals (margin, growth, FCF, leverage trends) outweigh a good story.
4. Prefer "hold" when evidence is mixed; upgrade to "keep" only with clear, multi-card agreement;
   downgrade to "sell" only with clear deterioration or valuation excess — never on one bad card alone.
5. State the specific falsifiers: what data, if it worsens next period, would move you to sell.

Return ONLY this JSON:
{{"recommendation": "hold|keep|sell",
  "confidence": 0.0-1.0,
  "justification": "4-7 sentences citing specific figures from specific cards",
  "falsifiers": ["...", "...", "..."]}}"""


def comment_cards(symbol: str, cards: list, tech: dict) -> None:
    for card in cards + [tech]:
        figs = "\n".join(f"- {label}: {val}" for label, val in card["figures"])
        series = ""
        if card.get("series"):
            series = "MULTI-YEAR SERIES (oldest first):\n" + json.dumps(card["series"])
        out = ai_json(CARD_PROMPT.format(symbol=symbol, card_name=card["name"],
                                         period=card["period"], figures=figs, series=series))
        card["commentary"] = out.get("commentary", "").strip()
        print(f"  commentary: {card['name']}")


def summarize(symbol: str, cards: list, tech: dict) -> dict:
    parts = []
    for card in cards + [tech]:
        figs = "; ".join(f"{l}={v}" for l, v in card["figures"])
        parts.append(f"REPORT: {card['name']} (period {card['period']})\nFIGURES: {figs}\n"
                     f"ANALYST COMMENTARY: {card.get('commentary','')}")
    out = ai_json(SUMMARY_PROMPT.format(symbol=symbol, bundle="\n\n".join(parts)))
    rec = str(out.get("recommendation", "hold")).lower()
    if rec not in ("hold", "keep", "sell"):
        rec = "hold"
    return {"recommendation": rec, "confidence": float(out.get("confidence", 0.5)),
            "justification": out.get("justification", ""),
            "falsifiers": [str(x) for x in out.get("falsifiers", [])]}


# ------------------------------------------------------------------ HTML
CSS = """
:root{--bg:#0b0d12;--panel:#14171f;--panel-2:#1a1e29;--border:rgba(190,180,160,.12);
  --text:#f0ece4;--muted:#9a938a;--gold:#d4af6a;--rose:#c98a8a;--sage:#8fae8f;--steel:#7f9bb3}
*{margin:0;padding:0;box-sizing:border-box}
body{background:radial-gradient(1100px 700px at 85% -10%,#1c1a24 0%,var(--bg) 55%);
  color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:26px 32px 48px}
header{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:18px}
header h1{font-size:22px;font-weight:650}header h1 span{color:var(--gold)}
header .meta{color:var(--muted);font-size:13px}
.verdict{border:1px solid var(--border);border-radius:14px;padding:20px 22px;margin-bottom:20px;
  background:linear-gradient(135deg,rgba(212,175,106,.10),rgba(212,175,106,.03))}
.verdict .badge{display:inline-block;padding:6px 18px;border-radius:999px;font-weight:700;
  font-size:15px;letter-spacing:.08em;text-transform:uppercase;color:#fff}
.verdict .badge.hold{background:#8a6a33}.verdict .badge.keep{background:#3f7d4f}.verdict .badge.sell{background:#a4453f}
.verdict .conf{color:var(--muted);font-size:12.5px;margin-left:12px}
.verdict p{margin-top:12px;line-height:1.65;font-size:14.5px}
.verdict ul{margin:10px 0 0 18px;color:var(--muted);font-size:13px;line-height:1.6}
.verdict b{color:var(--gold)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.card{background:linear-gradient(180deg,var(--panel-2),var(--panel));border:1px solid var(--border);
  border-radius:14px;padding:18px 20px}
.card.full{grid-column:1/-1}
.card h3{font-size:14.5px;font-weight:600}.card .sub{color:var(--muted);font-size:12px;margin:2px 0 12px}
.figures{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
.fig{background:rgba(255,255,255,.02);border:1px solid var(--border);border-radius:10px;padding:10px 12px}
.fig .l{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.8px}
.fig .v{font-size:19px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums}
.ai{margin-top:14px;background:linear-gradient(135deg,rgba(127,155,179,.10),rgba(127,155,179,.03));
  border:1px solid rgba(127,155,179,.18);border-radius:10px;padding:12px 14px;font-size:13.5px;line-height:1.6}
.ai b{color:var(--steel)}
#chart{width:100%;height:420px}
footer{margin-top:26px;color:var(--muted);font-size:12px;text-align:center}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
"""

def render_html(symbol: str, cards: list, tech: dict, verdict: dict, echarts_js: str, out_path: Path):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rec = verdict["recommendation"]

    def card_html(card, chart_div=""):
        figs = "".join(f'<div class="fig"><div class="l">{l}</div><div class="v">{v}</div></div>'
                       for l, v in card["figures"])
        return (f'<div class="card{ " full" if chart_div else ""}"><h3>{card["name"]}</h3>'
                f'<div class="sub">period: {card["period"]}</div>'
                f'<div class="figures">{figs}</div>{chart_div}'
                f'<div class="ai"><b>AI commentary</b><br>{card.get("commentary","")}</div></div>')

    chart_div = '<div id="chart"></div>'
    body = [f'<div class="verdict"><span class="badge {rec}">{rec.upper()}</span>'
            f'<span class="conf">confidence {verdict["confidence"]:.0%}</span>'
            f'<p><b>Summary verdict — all cards considered:</b> {verdict["justification"]}</p>']
    if verdict["falsifiers"]:
        body.append('<ul>' + "".join(f"<li>{x}</li>" for x in verdict["falsifiers"]) + '</ul>')
    body.append('</div>')
    body.append('<div class="grid">')
    body.append(card_html(tech, chart_div))
    for c in cards:
        body.append(card_html(c))
    body.append('</div>')

    dates = [b["t"] for b in tech["bars"]]
    ohlc = [[b["o"], b["c"], b["l"], b["h"]] for b in tech["bars"]]
    chart_js = f"""
var dates={json.dumps(dates)}, ohlc={json.dumps(ohlc)};
var bb={json.dumps(tech["bb"])};
var ch=echarts.init(document.getElementById('chart'));
ch.setOption({{
  backgroundColor:'transparent',
  tooltip:{{trigger:'axis',axisPointer:{{type:'cross'}}}},
  legend:{{data:['OHLC','BB ±2σ','BB ±3σ'],textStyle:{{color:'#9a938a'}},top:0}},
  grid:{{left:52,right:16,top:34,bottom:44}},
  xAxis:{{type:'category',data:dates,axisLine:{{lineStyle:{{color:'#3a3f4c'}}}},axisLabel:{{color:'#9a938a'}}}},
  yAxis:{{scale:true,axisLabel:{{color:'#9a938a'}},splitLine:{{lineStyle:{{color:'rgba(190,180,160,.08)'}}}}}},
  dataZoom:[{{type:'inside'}},{{type:'slider',height:18,bottom:8,borderColor:'#3a3f4c',
    textStyle:{{color:'#9a938a'}}}}],
  series:[
    {{name:'OHLC',type:'candlestick',data:ohlc,itemStyle:{{color:'#8fae8f',color0:'#c98a8a',
      borderColor:'#8fae8f',borderColor0:'#c98a8a'}}}},
    {{name:'BB ±2σ',type:'line',data:bb.u1,showSymbol:false,lineStyle:{{color:'#7f9bb3',width:1}},
      areaStyle:{{color:'rgba(127,155,179,.08)'}}}},
    {{type:'line',data:bb.l1,showSymbol:false,lineStyle:{{color:'#7f9bb3',width:1}}}},
    {{name:'BB ±3σ',type:'line',data:bb.u2,showSymbol:false,lineStyle:{{color:'#d4af6a',width:1,type:'dotted'}}}},
    {{type:'line',data:bb.l2,showSymbol:false,lineStyle:{{color:'#d4af6a',width:1,type:'dotted'}}}}
  ]
}});
window.addEventListener('resize',()=>ch.resize());
"""

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{symbol} — Trade Report</title><style>{CSS}</style></head>
<body>
<header><h1>{symbol} <span>// Trade Report</span></h1>
<div class="meta">generated {now} · fundamentals: finreports ETL · price: yfinance 120d</div></header>
{''.join(body)}
<footer>conservative desk view — evidence-proportional conviction; falsifiers listed above</footer>
<script>{echarts_js}</script>
<script>{chart_js}</script>
</body></html>"""
    out_path.write_text(html, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--db", default=FIN_DB_DEFAULT)
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()
    symbol = args.symbol.upper()

    import config as finconfig
    conn = finconfig.connect(args.db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM dbo.income_statement WHERE symbol=?", (symbol,))
    if cur.fetchone()[0] == 0:
        print(f"ABORT: {symbol} has no rows in {args.db} — run sync_fin_report_v2.py first")
        return 2

    print(f"[1/5] fundamentals from {args.db} ...")
    f = load_fundamentals(cur, symbol)
    conn.close()
    cards = build_cards(f)

    print(f"[2/5] price bars + double Bollinger ...")
    tech = build_technical(symbol)

    print(f"[3/5] per-card AI commentary ({AI_MODEL}) ...")
    comment_cards(symbol, cards, tech)

    print(f"[4/5] summary verdict ...")
    verdict = summarize(symbol, cards, tech)
    print(f"  verdict: {verdict['recommendation'].upper()} @ {verdict['confidence']:.0%}")

    print(f"[5/5] render HTML ...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) / f"{symbol}_report_v2.html"   # stable name: new run overwrites old
    render_html(symbol, cards, tech, verdict, ECHARTS_MIN.read_text(encoding="utf-8"), out)
    print(f"OK: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
