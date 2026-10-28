#!/usr/bin/env python
# build_index.py — scans reports/v2/*.html, extracts each verdict, writes index.html
# (jewelry style) linking every report. Run after generating reports.
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "reports" / "v2"

CSS = """
:root{--bg:#0b0d12;--panel:#14171f;--border:rgba(190,180,160,.12);--text:#f0ece4;
  --muted:#9a938a;--gold:#d4af6a;--steel:#7f9bb3}
*{margin:0;padding:0;box-sizing:border-box}
body{background:radial-gradient(1100px 700px at 85% -10%,#1c1a24 0%,var(--bg) 55%);
  color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;padding:26px 32px 48px}
header h1{font-size:22px;font-weight:650}header h1 span{color:var(--gold)}
header .meta{color:var(--muted);font-size:13px;margin-top:4px}
table{margin-top:20px;border-collapse:collapse;width:100%;max-width:760px}
th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.8px;
  text-align:left;padding:8px 12px;border-bottom:1px solid var(--border)}
td{padding:12px;border-bottom:1px solid var(--border);font-size:14.5px}
tr:hover td{background:rgba(255,255,255,.02)}
td.sym{font-weight:700;font-size:16px}
.badge{display:inline-block;padding:4px 14px;border-radius:999px;font-weight:700;
  font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#fff}
.badge.hold{background:#8a6a33}.badge.keep{background:#3f7d4f}.badge.sell{background:#a4453f}
a{color:var(--steel);text-decoration:none}a:hover{text-decoration:underline}
.conf{color:var(--muted);font-variant-numeric:tabular-nums}
"""

def main():
    rows = []
    for f in sorted(V2.glob("*_report_v2.html")):
        if f.name == "index.html":
            continue
        h = f.read_text(encoding="utf-8")
        m = re.search(r'class="badge (\w+)">\w+</span><span class="conf">confidence (\d+%)', h)
        gen = re.search(r'generated ([0-9: -]+)</div>', h)
        sym = f.stem.split("_report")[0]
        rows.append((sym, m.group(1) if m else "n/a", m.group(2) if m else "-",
                     gen.group(1).strip() if gen else "-", f.name))
    order = {"sell": 0, "keep": 1, "hold": 2, "n/a": 3}
    rows.sort(key=lambda r: (order[r[1]], r[0]))
    body = "".join(
        f'<tr><td class="sym">{s}</td><td><span class="badge {rec}">{rec}</span></td>'
        f'<td class="conf">{conf}</td><td>{gen}</td>'
        f'<td><a href="{link}">open report</a></td></tr>'
        for s, rec, conf, gen, link in rows)
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trade Reports — Index</title><style>{CSS}</style></head>
<body>
<header><h1>Trade Reports <span>// Index</span></h1>
<div class="meta">{len(rows)} reports · generated {datetime.now().strftime('%Y-%m-%d %H:%M')} ·
conservative desk view: HOLD / KEEP / SELL with falsifiers</div></header>
<table><tr><th>Ticker</th><th>Verdict</th><th>Confidence</th><th>Generated</th><th></th></tr>
{body}</table>
</body></html>"""
    out = V2 / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"OK: {out} ({len(rows)} reports)")

if __name__ == "__main__":
    main()
