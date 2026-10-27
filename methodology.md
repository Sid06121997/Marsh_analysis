# Methodology and data dictionary

## Coverage and sources

Eight required tickers: TRV, CB, PGR, ALL, ACGL, EG, RNR, WRB. CIKs are resolved from the SEC ticker map, never guessed. Company names and resolved identifiers are in `data/companies.json`. Financial data cover five fiscal years, 2021-2025, with 2020 retained in the base table to calculate opening equity and first-year growth. All eight issuers have 31 December fiscal year ends in this sample. Text analysis uses the three most recent distinct annual 10-K report dates, 2023-2025, selected by filing date through 2026-10-21. Amendments are not treated as additional annual text observations.

The sources are [SEC company tickers](https://www.sec.gov/files/company_tickers.json), the SEC companyfacts and submissions endpoints, primary filing HTML, and Progressive's linked annual-report exhibit. Exact URLs and accessions are included in the output audits and filing inventory. Source responses are cached unchanged with hashes. A current companyfacts response cannot reproduce facts later removed from the API; filtering filing dates limits but does not eliminate this point-in-time limitation.

## Financial extraction and calculations

For each preferred standard tag, select facts with the exact fiscal endpoint, form 10-K or 10-K/A, and filing date no later than the cutoff. Flow metrics must span 330-380 days; balance-sheet equity is an instant. Choose the most recently filed observation, then accession number as a deterministic tie-breaker. This uses the latest available comparative/restated value, not necessarily the originally published value. Tag fallback order is explicit in `analysis.py`. Preserve missing values rather than converting them to zero.

Companyfacts does not include all dimensional disclosures. Allstate's P&C net written premiums are extracted from the inline `us-gaap:PremiumsWrittenNet` fact with the PropertyLiabilityAndCasualtyInsuranceSegmentMember dimension. It includes Protection Services P&C premiums, while the displayed combined ratio is for Property-Liability. Chubb's group premium total includes life; Arch's includes mortgage insurance. These are disclosed group-level comparisons, not a homogeneous P&C-only cohort.

| Field | Definition and unit |
|---|---|
| `ticker`, `company`, `fiscal_year`, `period_end` | Company and annual-period key |
| `net_written_premiums` | Net written premiums, USD; scope in `premium_scope` |
| `net_income` | Net income attributable to parent when `NetIncomeLoss` is used; USD |
| `equity` | Year-end stockholders' equity; USD, including preferred equity where present |
| `average_equity` | Arithmetic mean of current and previous year-end equity |
| `roe_pct` | 100 x net income / average equity; only positive average equity allowed |
| `revenue` | Consolidated reported total revenue, USD |
| `net_profit_margin_pct` | 100 x net income / revenue |
| `premium_growth_pct` | 100 x (current / prior net written premiums - 1) |
| `revenue_growth_pct`, `equity_growth_pct` | Same growth formula; prior value must be positive |
| `combined_ratio_pct` | Sum of disclosed loss and underwriting expense ratios, percent |
| `combined_ratio_scope` | Business scope of the ratio; see below |
| `premiums_earned`, `losses_and_lae`, `acquisition_costs` | Additional standard-tag facts, USD; may be missing or have a different group scope; not used to synthesize combined ratios |

ROE is not return on common equity or a company's adjusted operating ROE. It includes reported investment results and one-off effects. Allstate's 2025 earnings include disposal gains. Revenue growth is not premium growth: investment returns and other income can produce a different direction, as at RenaissanceRe. Growth is nominal and not adjusted for acquisitions, foreign exchange, or portfolio changes.

### Combined ratios

Derive the ratio by adding disclosed loss and expense ratios, and compare against the separately reported combined ratio. A difference up to 0.21 percentage points is allowed because independently rounded components can differ by 0.1-0.2 points. Retain both totals and the difference in `combined_ratio_audit.csv`; derived values are not silently replaced by reported values.

Travelers, Progressive, Everest, RenaissanceRe, and W. R. Berkley use consolidated underwriting totals. Chubb uses P&C underwriting only. Allstate uses Property-Liability. Arch uses insurance, reinsurance, and mortgage underwriting, excluding corporate and other. These definitions differ; ratios are useful screening measures, not a fully harmonized ranking.

Tables in the 2025 and 2022 filings supply comparative values spanning 2020-2025. Arch and RenaissanceRe use explicitly consolidated inline-XBRL ratios. Arch changed tag names, so documented aliases are used. Progressive's table is in its annual-report exhibit. Everest's 2022 filing uses positioned divs, requiring a text-pattern fallback. The latest selected comparative disclosure wins. This supplemental rule is narrower than the companyfacts restatement rule: intervening revisions not reproduced in those selected filings may be missed. Source rows, URLs, and filing dates remain available for review.

## Text extraction and measurement

Remove script, style, hidden elements, and inline-XBRL headers, then normalize whitespace. Match Item 1A through Item 1B, Item 1C, or Item 2; match Item 7 through Item 7A or Item 8. Require recognizable section titles and minimum lengths (700 words for Risk Factors; 1,000 for MD&A). Reject short table-of-contents spans and quoted/dash-separated cross-references. Enforce section order and choose the longest remaining plausible span. Allstate repeats its Risk Factors running heading; the longest span preserves the complete section.

Progressive incorporates MD&A by reference. Follow the explicit Annual Report to Shareholders link, starting at the MD&A title and stopping before the Safe Harbor statement. This excludes the exhibit's subsequent market-risk section and gives a consistent boundary across its three years. Other companies' boilerplate, numeric tables, and running headers within the sections are retained. Denominators therefore measure extracted word tokens, including numeric tokens, not pure narrative prose. This can influence comparisons when table density or boilerplate changes. All 48 section starts and ends were reviewed; Travelers cross-reference errors were corrected before final analysis.

Use case-insensitive, non-overlapping regex matches with word boundaries. The six dictionaries are defined in `analysis.py` and follow the assignment's examples. Minor plural variants are allowed; `cyber` matches cyber-prefixed words, including cybersecurity and cybercrime. The AI dictionary is exactly artificial intelligence, machine learning, and automation; it intentionally excludes ambiguous standalone AI. Phrases may miss synonyms and negation. A sentence can match multiple themes; counts are not mutually exclusive.

| Dataset or field | Interpretation |
|---|---|
| `case3_section_theme_counts.csv` | 288 rows: 8 companies x 3 years x 2 sections x 6 themes |
| `mentions` | Number of matching phrase occurrences, not number of paragraphs |
| `words` | Regex word-token count for the section; repeated once per theme |
| `mentions_per_1000_words` | 1,000 x mentions / words |
| `case3_theme_matrix.csv` | 144 rows, adding counts and denominators across the two sections within each company-year-theme |
| `case3_peer_trends.csv` | Equal-weight mean of the eight company rates, not pooled text counts |
| `case3_theme_changes.csv` | 2025 minus 2023 absolute rate change and percentage change from 2023 |
| `case3_sentence_evidence.csv` | Exact sentences, section-relative offsets, year, theme, and source URL |

Do not sum the repeated `words` field across themes. Percentage growth from a zero company baseline is undefined; it is not reported as infinity. The theme change memo defines both absolute and relative growth because they yield different leaders. Disclosure frequency is a screening signal, not a probability of loss, financial materiality, or proof of technology adoption. Three observations per company support descriptive trends, not causal or statistically robust time-series inference.
