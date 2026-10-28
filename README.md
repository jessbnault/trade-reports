# trade-reports

Conservative trade reports — **click any ticker below to view it as a live rendered page** (GitHub Pages). No downloads, no fiddling.

## Reports

| Ticker |
|---|
| [AAPL](https://jessbnault.github.io/trade-reports/reports/AAPL_report_v2.html) |
| [ADBE](https://jessbnault.github.io/trade-reports/reports/ADBE_report_v2.html) |
| [AMZN](https://jessbnault.github.io/trade-reports/reports/AMZN_report_v2.html) |
| [CSCO](https://jessbnault.github.io/trade-reports/reports/CSCO_report_v2.html) |
| [HOOD](https://jessbnault.github.io/trade-reports/reports/HOOD_report_v2.html) |
| [INTC](https://jessbnault.github.io/trade-reports/reports/INTC_report_v2.html) |
| [META](https://jessbnault.github.io/trade-reports/reports/META_report_v2.html) |
| [MSFT](https://jessbnault.github.io/trade-reports/reports/MSFT_report_v2.html) |
| [NOK](https://jessbnault.github.io/trade-reports/reports/NOK_report_v2.html) |
| [NVDA](https://jessbnault.github.io/trade-reports/reports/NVDA_report_v2.html) |
| [PLTR](https://jessbnault.github.io/trade-reports/reports/PLTR_report_v2.html) |
| [SHOP](https://jessbnault.github.io/trade-reports/reports/SHOP_report_v2.html) |
| [SONY](https://jessbnault.github.io/trade-reports/reports/SONY_report_v2.html) |
| [TSLA](https://jessbnault.github.io/trade-reports/reports/TSLA_report_v2.html) |
| [TSM](https://jessbnault.github.io/trade-reports/reports/TSM_report_v2.html) |
| [UBER](https://jessbnault.github.io/trade-reports/reports/UBER_report_v2.html) |

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
