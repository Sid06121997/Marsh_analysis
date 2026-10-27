# Technology and AI Analyst case study submission

Completed Case Study 1 and mandatory Case Study 3. This follows the instruction to choose exactly two cases; Case Study 2 is not part of this submission.

## Read first

[Read the business memos](business_memos.pdf) | [View the charts](charts/) | [Browse the datasets](data/)


- `business_memos.pdf`: one page per case, with findings and recommendations.
- `data/case1_financials.csv`: 40 company-year records, fiscal 2021-2025.
- `data/case1_latest_rankings.csv`: all eight companies ranked for fiscal 2025.
- `data/case3_theme_matrix.csv`: 144 company-year-theme records, fiscal 2023-2025, combining Risk Factors and MD&A.
- `charts/`: three financial charts and two risk-language charts. Five files satisfy the case-specific minimums (three plus two), which exceed the general 2-4 chart suggestion.
- `sentence_evidence.md`: three actual sentences illustrating Travelers' changing AI disclosure.
- `methodology.md`: formulas, source selection, extraction rules, limitations, and data dictionary.
- `llm_upgrade.md`: proposed prompt, output schema, and evaluation plan; no API key required.

## Repository contents

This repository includes all required deliverables and extracted section text. The large raw SEC download cache is omitted. Existing CSVs, charts, and memos can be reviewed immediately. Rebuilding from source requires internet access and your own descriptive SEC User-Agent. The original full archive retains the source cache for exact offline reproduction.

## Run the Python project

Python 3.12 was used. Create a virtual environment:

```text
python -m venv .venv
```

Activate it before installing or running. On Windows PowerShell use `.venv\Scripts\Activate.ps1`; on macOS/Linux use `source .venv/bin/activate`. Then install dependencies:

```text
python -m pip install -r requirements.txt
```

Set your SEC contact before running from the extracted submission folder (PowerShell):

```powershell
$env:SEC_USER_AGENT = 'Your Name your.email@example.com'
```

```text
python analysis.py --as-of 2026-10-21
python summarize.py
python test_analysis.py
python build_memos.py
```

The first command downloads the SEC sources and creates a local cache. For a subsequent fresh download, use a separate cache directory (PowerShell example):

```powershell
$env:SEC_USER_AGENT = 'Your Name your.email@example.com'
python analysis.py --cache new_cache --as-of 2026-10-21
python summarize.py
```

On macOS/Linux use `export SEC_USER_AGENT='Your Name your.email@example.com'`. Never commit contact details or API keys. The included source manifest contains source URLs, retrieval timestamps, and hashes, but no User-Agent contact information.

`--as-of` is a filing-date cutoff, not a prediction of future reporting. The delivered snapshot uses 21 October 2026 and the latest annual filings then available, covering fiscal 2025. A new cache is required to refresh sources; existing cached responses are reused deliberately. Older arbitrary cutoffs may require additional filing-history downloads. Narrative memos describe the delivered snapshot and must be reviewed if the input period changes. The supplemental table rules are tailored to this eight-company, five-year sample; changed filing layouts fail rather than silently guessing.

The client sends a descriptive User-Agent for every request, spaces requests by at least 0.3 seconds, caches responses, and retries transient server errors with backoff. No LLM API was used.

## Contents and validation

`analysis.py` resolves tickers, retrieves financial facts and filing histories, extracts sections, computes metrics, and saves charts. `filing_metrics.py` handles inline XBRL and issuer-specific underwriting tables. `summarize.py` generates change statistics and traceable sentence evidence. `build_memos.py` creates the PDF and editable Markdown memos using Python.

Seven automated tests passed, covering annual-period selection, restatements, table-of-contents rejection, keyword boundaries, complete output coverage, calculations, exact quotations, and source hashes. The full project was successfully rerun offline from its source cache during validation; that cache is omitted from this repository. All five charts and both memo pages were visually reviewed.

`data/financial_fact_audit.csv`, `data/supplemental_fact_audit.csv`, and `data/combined_ratio_audit.csv` retain provenance and calculation components. `data/section_quality.csv` records word counts and extraction boundaries for all 48 sections. `sections/` contains normalized extracted text. `data/source_manifest.csv` maps source URLs to retrieval timestamps and SHA-256 hashes; the cache uses hashed URL filenames. No missing values were imputed in the analysis.

The original assignment is not redistributed in this package. No submission was sent to an employer or other third party.
