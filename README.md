# trade-reports

Full index with verdicts & confidence: **[report index](https://jessbnault.github.io/trade-reports/reports/)**

## How it works

- `reports/index.html` — index of all reports with HOLD/KEEP/SELL verdict + confidence
- `reports/<TICKER>_report_v2.html` — stable filenames; reruns overwrite in place
- `scripts/report_v2.py` — generator: fundamentals from the local `finreports` SQL Server ETL,
  120-day double Bollinger candlestick, per-card AI commentary, and a summary AI call that
  weighs every card into one conservative HOLD / KEEP / SELL verdict with falsifiers
- `scripts/build_index.py` — rebuilds the index page
- `scripts/one_shot.py` — full pipeline: sync → report → index → push (Pages redeploys automatically)

Requires: SQL Server `finreports` DB, a local or OpenRouter LLM endpoint (keys via env only).
