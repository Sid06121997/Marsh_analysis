"""Build change tables and exact source-sentence evidence from pipeline outputs."""
from pathlib import Path
import re
import pandas as pd
ROOT=Path(__file__).resolve().parent

def main():
    matrix=pd.read_csv(ROOT/'data/case3_theme_matrix.csv')
    peer=pd.read_csv(ROOT/'data/case3_peer_trends.csv')
    change=peer.pivot(index='theme',columns='fiscal_year',values='mentions_per_1000_words')
    first,last=min(change.columns),max(change.columns)
    change['absolute_change']=change[last]-change[first]
    change['relative_change_pct']=100*(change[last]/change[first]-1)
    change.sort_values('absolute_change',ascending=False).to_csv(ROOT/'data/case3_theme_changes.csv')
    q=pd.read_csv(ROOT/'data/section_quality.csv')
    chosen={2024:['In addition, new technology, such as artificial intelligence, could create unforeseen'],
            2025:['Artificial intelligence, in particular, may become more expensive',
                  'Regarding artificial intelligence, legal and regulatory frameworks are developing']}
    evidence=[]
    for year,starts in chosen.items():
        path=ROOT/'sections'/f'TRV_{year}_item1A.txt';text=path.read_text(encoding='utf-8')
        for start in starts:
            begin=text.index(start);end=text.index('.',begin)+1;sentence=text[begin:end]
            source=q[(q.ticker=='TRV')&(q.fiscal_year==year)&(q.section=='1A')].iloc[0]
            evidence.append({'ticker':'TRV','fiscal_year':year,'section':'1A','theme':'Technology and AI',
                'sentence':sentence,'start_char_in_section':begin,'end_char_in_section':end,'url':source.url})
    pd.DataFrame(evidence).to_csv(ROOT/'data/case3_sentence_evidence.csv',index=False)
    parts=['# Travelers technology and AI disclosure evidence\n',
           'Three verbatim sentences from Item 1A. Whitespace is normalized during HTML extraction.\n']
    for row in evidence:
        parts += [f'## Fiscal {row["fiscal_year"]}\n',f'> {row["sentence"]}\n',f'[SEC filing]({row["url"]})\n']
    parts+=['## Interpretation\n',
      'The 2024 sentence already identifies coverage and fraud exposure. The two 2025 sentences add explicit cost and regulatory uncertainty. Both 2025 sentences are absent verbatim from the extracted 2024 Item 1A; that does not prove the underlying concepts were entirely new. More mentions measure disclosure emphasis, not successful adoption or increased realized losses.\n']
    (ROOT/'sentence_evidence.md').write_text('\n'.join(parts),encoding='utf-8')
    print(change.round(5).to_string())
    print(matrix[(matrix.ticker=='TRV')&(matrix.theme=='Technology and AI')].to_string(index=False))

if __name__=='__main__': main()
