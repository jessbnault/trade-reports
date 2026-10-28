# trade-reports

Conservative trade reports in a single self-contained HTML file.

- `reports/AMZN_report_v2.html` — AMZN report (verdict: HOLD @ 68%)
- `scripts/report_v2.py` — generator: fundamentals from the local `finreports` SQL Server ETL,
  120-day double Bollinger candlestick, per-card AI commentary, and a summary AI call that
  weighs every card into one conservative HOLD / KEEP / SELL verdict with falsifiers.

Requires: SQL Server `finreports` DB, a local or OpenRouter LLM endpoint (keys via env only).
