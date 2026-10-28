# trade-reports

Conservative trade reports, one self-contained HTML file per ticker.

- `reports/index.html` — index of all reports with verdict + confidence
- `reports/<TICKER>_report_v2.html` — stable filenames; reruns overwrite
- `scripts/report_v2.py` — generator: fundamentals from the local `finreports` SQL Server ETL,
  120-day double Bollinger candlestick, per-card AI commentary, and a summary AI call that
  weighs every card into one conservative HOLD / KEEP / SELL verdict with falsifiers.
- `scripts/build_index.py` — rebuilds the index page from the reports folder

Requires: SQL Server `finreports` DB, a local or OpenRouter LLM endpoint (keys via env only).
