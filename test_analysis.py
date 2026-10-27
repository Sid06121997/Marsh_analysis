"""Unit regressions plus end-to-end output integrity checks; run after analysis.py."""
import unittest,re,json,hashlib
import pandas as pd
import numpy as np
from analysis import ROOT,annual_fact,extract_sections,count_themes,COMPANIES

class RegressionTests(unittest.TestCase):
    def test_latest_annual_not_quarter_or_future(self):
        facts={'facts':{'us-gaap':{'NetIncomeLoss':{'units':{'USD':[
          {'start':'2024-01-01','end':'2024-12-31','form':'10-K','filed':'2025-02-01','val':10},
          {'start':'2024-01-01','end':'2024-12-31','form':'10-K/A','filed':'2025-03-01','val':12},
          {'start':'2024-10-01','end':'2024-12-31','form':'10-K','filed':'2025-04-01','val':99},
          {'start':'2024-01-01','end':'2024-12-31','form':'10-K','filed':'2027-02-01','val':88}]}}}}}
        self.assertEqual(annual_fact(facts,['NetIncomeLoss'],'2024-12-31',asof='2026-10-21')[0],12)
    def test_toc_and_cross_reference_rejected(self):
        text=('Item 1A. Risk Factors 10 Item 1B. Unresolved Staff Comments 20 '
              'See Item 1A—Risk Factors.” '+('business '*900)+
              'Item 1A. RISK FACTORS '+('risk '*800)+'Item 1B. UNRESOLVED STAFF COMMENTS None. '+
              'Item 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS '+
              ('results '*1100)+'Item 7A. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK')
        sections=extract_sections(text)
        self.assertTrue(sections['1A']['text'].startswith('Item 1A. RISK FACTORS'))
        self.assertLess(len(sections['1A']['text'].split()),810)
    def test_keyword_boundaries_and_case(self):
        results={x['theme']:x['mentions'] for x in count_themes('ARTIFICIAL INTELLIGENCE and machine learning. Cybersecurity ransomware hurricane hurricanes. Not automationism.')}
        self.assertEqual(results['Technology and AI'],2)
        self.assertEqual(results['Cyber risk'],2)
        self.assertEqual(results['Catastrophe and climate'],2)

class OutputTests(unittest.TestCase):
    def test_financial_coverage_and_calculations(self):
        d=pd.read_csv(ROOT/'data/case1_financials.csv')
        self.assertEqual(len(d),40);self.assertEqual(len(d[['ticker','fiscal_year']].drop_duplicates()),40)
        self.assertEqual(set(d.ticker),set(COMPANIES))
        required=['roe_pct','net_profit_margin_pct','premium_growth_pct','revenue_growth_pct','equity_growth_pct','combined_ratio_pct','net_written_premiums']
        self.assertFalse(d[required].isna().any().any())
        np.testing.assert_allclose(d.roe_pct,d.net_income/d.average_equity*100)
        ratios=pd.read_csv(ROOT/'data/combined_ratio_audit.csv')
        self.assertTrue((ratios.rounding_difference_pp.abs()<=.21).all())
    def test_text_coverage_and_denominators(self):
        d=pd.read_csv(ROOT/'data/case3_section_theme_counts.csv'); self.assertEqual(len(d),288)
        self.assertEqual(len(d[['ticker','fiscal_year','section','theme']].drop_duplicates()),288)
        self.assertTrue((d.words>700).all()); self.assertTrue((d.mentions>=0).all())
        np.testing.assert_allclose(d.mentions_per_1000_words,1000*d.mentions/d.words)
        self.assertEqual(len(pd.read_csv(ROOT/'data/case3_theme_matrix.csv')),144)
        for year in [2023,2024,2025]:
            body=(ROOT/'sections'/f'TRV_{year}_item1A.txt').read_text(encoding='utf-8')
            self.assertTrue(body.startswith('Item 1A. RISK FACTORS'))
            self.assertNotIn('Claims — Paying Ratings',body[:200])
    def test_evidence_exact(self):
        d=pd.read_csv(ROOT/'data/case3_sentence_evidence.csv');self.assertEqual(len(d),3)
        for _,r in d.iterrows():
            text=(ROOT/'sections'/f'{r.ticker}_{r.fiscal_year}_item{r.section}.txt').read_text(encoding='utf-8')
            self.assertEqual(text[r.start_char_in_section:r.end_char_in_section],r.sentence)
    def test_cached_source_hashes(self):
        for meta in (ROOT/'cache').glob('*.json'):
            record=json.loads(meta.read_text());payload=meta.with_suffix('.bin').read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(),record['sha256'])

if __name__=='__main__': unittest.main(verbosity=2)
