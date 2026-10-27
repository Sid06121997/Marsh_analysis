"""Reproducible SEC insurance peer analysis. See README.md for use and definitions."""
from __future__ import annotations
import argparse, hashlib, json, os, re, time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings('ignore',category=XMLParsedAsHTMLWarning)

ROOT = Path(__file__).resolve().parent
COMPANIES = {'TRV':'Travelers','CB':'Chubb','PGR':'Progressive','ALL':'Allstate',
             'ACGL':'Arch Capital','EG':'Everest','RNR':'RenaissanceRe','WRB':'W. R. Berkley'}
THEMES = {
 'Catastrophe and climate': [r'catastrophe losses',r'climate change',r'hurricanes?',r'severe weather'],
 'Reinsurance and recoverables':[r'reinsurance recoverables?',r'retrocession',r'counterparty credit risk'],
 'Social inflation and litigation':[r'social inflation',r'litigation trends?',r'nuclear verdicts?',r'claims severity'],
 'Reserve adequacy':[r'reserve development',r'adverse development',r'loss reserves?'],
 'Cyber risk':[r'cyber\w*',r'data breaches?',r'ransomware'],
 'Technology and AI':[r'artificial intelligence',r'machine learning',r'automation']}

class SECClient:
    def __init__(self, cache, user_agent, offline=False):
        self.cache=Path(cache); self.cache.mkdir(parents=True,exist_ok=True)
        self.offline=offline; self.last=0
        self.headers={'User-Agent':user_agent}
        self.manifest=[]
    def get(self,url):
        key=hashlib.sha256(url.encode()).hexdigest()
        path=self.cache/(key+'.bin'); meta=self.cache/(key+'.json')
        if not path.exists():
            if self.offline: raise FileNotFoundError(f'Missing cached source: {url}')
            if not self.headers['User-Agent'] or '@' not in self.headers['User-Agent']:
                raise ValueError('Set SEC_USER_AGENT to your real name and contact email.')
            for attempt in range(4):
                time.sleep(max(0,0.3-(time.monotonic()-self.last)))
                try:
                    with urlopen(Request(url,headers=self.headers),timeout=90) as response:
                        payload=response.read()
                    self.last=time.monotonic(); break
                except HTTPError as error:
                    self.last=time.monotonic()
                    if error.code not in (429,500,502,503,504) or attempt==3: raise
                    time.sleep(2**attempt*3)
            path.write_bytes(payload)
            meta.write_text(json.dumps({'url':url,'retrieved_utc':datetime.now(timezone.utc).isoformat(),
                'sha256':hashlib.sha256(payload).hexdigest()},indent=2))
        self.manifest.append(json.loads(meta.read_text()))
        return path.read_bytes()
    def json(self,url): return json.loads(self.get(url))

def resolve_companies(client):
    mapping=client.json('https://www.sec.gov/files/company_tickers.json')
    values=list(mapping.values())
    out={}
    for ticker,name in COMPANIES.items():
        matches=[x for x in values if x['ticker']==ticker]
        if len(matches)!=1: raise ValueError(f'Cannot uniquely resolve {ticker}')
        out[ticker]={'name':name,'cik':int(matches[0]['cik_str']),'sec_title':matches[0]['title']}
    return out

def select_filings(client,cik,asof,n=5):
    data=client.json(f'https://data.sec.gov/submissions/CIK{cik:010}.json')
    rows=pd.DataFrame(data['filings']['recent'])
    def eligible(df):
        return df[(df.form=='10-K') & (df.filingDate<=asof)].sort_values('filingDate',ascending=False).drop_duplicates('reportDate')
    for old in data['filings'].get('files',[]):
        if len(eligible(rows))>=n: break
        rows=pd.concat([rows,pd.DataFrame(client.json('https://data.sec.gov/submissions/'+old['name']))],ignore_index=True)
    result=eligible(rows).head(n).copy()
    if len(result)<n: raise ValueError(f'Only {len(result)} annual filings for CIK {cik}')
    result['url']=[f'https://www.sec.gov/Archives/edgar/data/{cik}/{a.replace("-","")}/{p}'
                   for a,p in zip(result.accessionNumber,result.primaryDocument)]
    return result

def annual_fact(facts,tags,end,instant=False,asof='9999-12-31'):
    """Prefer tag order; latest 10-K/10-K/A filed value for same exact fiscal endpoint."""
    for tag in tags:
        candidates=[]
        for fact in facts.get('facts',{}).get('us-gaap',{}).get(tag,{}).get('units',{}).get('USD',[]):
            if fact.get('end')!=end or fact.get('form') not in ('10-K','10-K/A') or fact.get('filed','')>asof: continue
            if not instant:
                if 'start' not in fact: continue
                days=(date.fromisoformat(end)-date.fromisoformat(fact['start'])).days
                if not 330<=days<=380: continue
            candidates.append(fact)
        if candidates:
            chosen=max(candidates,key=lambda x:(x.get('filed',''),x.get('accn','')))
            return chosen['val'],tag,chosen.get('accn',''),chosen.get('filed','')
    return np.nan,'','',''

def html_blocks(html):
    soup=BeautifulSoup(html,'lxml')
    for tag in soup.find_all(['script','style','ix:header']): tag.decompose()
    for tag in soup.find_all(style=True):
        if re.search(r'display\s*:\s*none',tag.get('style',''),re.I): tag.decompose()
    text=soup.get_text(' ',strip=True)
    return re.sub(r'\s+',' ',text).replace('\xa0',' ')

def extract_sections(text, labels=('1A','7')):
    """Find repeated Item headers; choose longest plausible heading-to-next-heading span.
    Removes TOC candidates using minimum lengths. Fails loudly on short/missing sections.
    """
    heading=re.compile(r'\bITEM\s+(1A|1B|1C|2|7A|7|8)\s*[.\-:–—]?\s*',re.I)
    matches=list(heading.finditer(text)); result={}
    def is_heading(m):
        if any(dash in m.group() for dash in ('—','–')): return False
        lead=text[m.end():m.end()+180]
        title=re.match(r'(Risk\s+Factors|Management[’\']s Discussion and Analysis of Financial Condition and Results of Operations?|Unresolved Staff Comments|Cybersecurity|Properties|Quantitative and Qualitative Disclosures About Market Risk|Financial Statements and Supplementary Data)',lead,re.I)
        if not title: return False
        tail=lead[title.end():].lstrip()
        if tail and tail[0] in '”’\"\'—–,-': return False
        if re.match(r'\.[”’\"\']',tail): return False
        if text[max(0,m.start()-1):m.start()] in ('“','"'): return False
        return True
    for label,stops,min_words in [('1A',{'1B','1C','2'},700),('7',{'7A','8'},1000)]:
        if label not in labels: continue
        candidates=[]
        for i,m in enumerate(matches):
            if m.group(1).upper()!=label: continue
            if label=='7' and '1A' in result and m.start()<result['1A']['end_char']: continue
            if not is_heading(m): continue
            # Heading must have expected title, avoiding references such as "Item 1A of this report".
            lead=text[m.end():m.end()+120].lower()
            if label=='1A' and not re.match(r'risk\s+factors',lead): continue
            if label=='7' and not re.match(r'management',lead): continue
            for end in matches[i+1:]:
                if end.group(1).upper() not in stops: continue
                if not is_heading(end): continue
                endlead=text[end.end():end.end()+100].lower()
                valid= re.match(r'(unresolved|cybersecurity|properties|quantitative|financial\s+statements)',endlead)
                if not valid: continue
                body=text[m.start():end.start()]
                if len(re.findall(r'\b\w+\b',body))>=min_words:
                    candidates.append((len(body),body,m.start(),end.start()))
                break
        if not candidates: raise ValueError(f'Could not extract plausible Item {label}')
        _,body,start,end=max(candidates)
        result[label]={'text':body,'start_char':start,'end_char':end,'candidate_count':len(candidates)}
    if '1A' in result and '7' in result and result['1A']['end_char']>result['7']['start_char']: raise ValueError('Sections overlap')
    return result

def count_themes(text):
    words=len(re.findall(r'\b\w+\b',text))
    rows=[]
    for theme,terms in THEMES.items():
        pattern=re.compile(r'\b(?:'+ '|'.join(terms)+r')\b',re.I)
        matches=list(pattern.finditer(text))
        rows.append({'theme':theme,'mentions':len(matches),'words':words,
                     'mentions_per_1000_words':1000*len(matches)/words})
    return rows

def financials(client,companies,filings,asof,out):
    rows=[]; audit=[]
    tags={
      'net_written_premiums':['PremiumsWrittenNet'],
      'net_income':['NetIncomeLoss','ProfitLoss'],
      'equity':['StockholdersEquity','StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
      'revenue':['Revenues','RevenueFromContractWithCustomerIncludingAssessedTax','SalesRevenueNet','RevenuesNetOfInterestExpense'],
      'premiums_earned':['PremiumsEarnedNet','InsuranceServicesRevenue'],
      'losses_and_lae':['PolicyholderBenefitsAndClaimsIncurredNet'],
      'acquisition_costs':['DeferredPolicyAcquisitionCostAmortizationExpense']}
    for ticker,co in companies.items():
        facts=client.json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{co["cik"]:010}.json')
        ends=sorted(filings[ticker].reportDate.tolist())
        # Opening balance and growth base are needed for first displayed fiscal year.
        first=date.fromisoformat(ends[0]); ends=[first.replace(year=first.year-1).isoformat()]+ends
        for end in ends:
            row={'ticker':ticker,'company':co['name'],'fiscal_year':int(end[:4]),'period_end':end}
            for metric,choices in tags.items():
                value,tag,accn,filed=annual_fact(facts,choices,end,metric=='equity',asof)
                row[metric]=value
                audit.append({'ticker':ticker,'period_end':end,'metric':metric,'value':value,
                              'tag':tag,'accession':accn,'filed':filed,'source':'SEC companyfacts'})
            rows.append(row)
    frame=pd.DataFrame(rows).sort_values(['ticker','period_end'])
    frame.to_csv(out/'financial_base.csv',index=False)
    pd.DataFrame(audit).to_csv(out/'financial_fact_audit.csv',index=False)
    return frame

def derive_financials(frame,out):
    frame=frame.sort_values(['ticker','period_end']).copy()
    grouped=frame.groupby('ticker',sort=False)
    frame['average_equity']=(frame.equity+grouped.equity.shift())/2
    frame['roe_pct']=100*frame.net_income/frame.average_equity.where(frame.average_equity>0)
    frame['net_profit_margin_pct']=100*frame.net_income/frame.revenue.where(frame.revenue>0)
    for col,label in [('revenue','revenue_growth_pct'),('equity','equity_growth_pct'),('net_written_premiums','premium_growth_pct')]:
        prior=grouped[col].shift()
        frame[label]=100*(frame[col]/prior.where(prior>0)-1)
    if 'combined_ratio_pct' not in frame: frame['combined_ratio_pct']=np.nan
    frame=frame.groupby('ticker',group_keys=False).tail(5)
    frame.to_csv(out/'case1_financials.csv',index=False)
    common=set.intersection(*(set(g.fiscal_year) for _,g in frame.groupby('ticker')))
    latest=frame[frame.fiscal_year==max(common)].copy()
    for metric in ['roe_pct','premium_growth_pct','net_profit_margin_pct']:
        latest[metric+'_rank']=latest[metric].rank(ascending=False,method='min')
    latest.to_csv(out/'case1_latest_rankings.csv',index=False)
    return frame,latest

def savefig(fig,path):
    fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white'); plt.close(fig)

def charts(fin,latest,risks,out):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold'})
    fig,ax=plt.subplots(figsize=(11,6))
    for ticker,g in fin.groupby('ticker'): ax.plot(g.fiscal_year,g.roe_pct,marker='o',label=ticker)
    ax.set(title='Return on average equity across insurance peers',xlabel='Fiscal year',ylabel='ROE (%)')
    ax.set_xticks(sorted(fin.fiscal_year.unique())); ax.axhline(0,color='#bbb',lw=.7)
    ax.legend(ncol=4,loc='upper center',bbox_to_anchor=(.5,-.13)); ax.grid(axis='y',alpha=.2)
    savefig(fig,out/'case1_roe.png')
    rank=latest.sort_values('net_profit_margin_pct')
    fig,ax=plt.subplots(figsize=(10,6)); ax.barh(rank.ticker,rank.net_profit_margin_pct,color='#245978')
    for y,(_,r) in enumerate(rank.iterrows()):
        if pd.notna(r.net_profit_margin_pct): ax.text(r.net_profit_margin_pct+.2,y,f'{r.net_profit_margin_pct:.1f}%',va='center')
    ax.set(title=f'Net profit margin ranking in {int(latest.fiscal_year.iloc[0])}',xlabel='Net income / total revenue (%)')
    ax.margins(x=.15); savefig(fig,out/'case1_margin.png')
    fig,ax=plt.subplots(figsize=(10,6)); ax.scatter(latest.revenue_growth_pct,latest.roe_pct,s=90,color='#245978')
    for _,r in latest.iterrows():
        if pd.notna(r.revenue_growth_pct) and pd.notna(r.roe_pct): ax.annotate(r.company,(r.revenue_growth_pct,r.roe_pct),xytext=(5,5),textcoords='offset points',fontsize=9)
    ax.set(title=f'Growth and profitability in {int(latest.fiscal_year.iloc[0])}',xlabel='Revenue growth (%)',ylabel='ROE (%)')
    ax.set_xlim(left=-1,right=latest.revenue_growth_pct.max()+3.5)
    ax.axvline(0,color='#bbb',lw=.7); ax.axhline(0,color='#bbb',lw=.7); ax.grid(alpha=.15)
    savefig(fig,out/'case1_growth_roe.png')
    # Each company contributes equally; combine its two sections before averaging.
    combined=risks.groupby(['ticker','fiscal_year','theme'],as_index=False)[['mentions','words']].sum()
    combined['mentions_per_1000_words']=combined.mentions/combined.words*1000
    combined.to_csv(out.parent/'data'/'case3_theme_matrix.csv',index=False)
    peer=combined.groupby(['fiscal_year','theme'],as_index=False).mentions_per_1000_words.mean()
    peer.to_csv(out.parent/'data'/'case3_peer_trends.csv',index=False)
    fig,axes=plt.subplots(1,2,figsize=(13,5.5))
    for ax,theme in zip(axes,['Catastrophe and climate','Technology and AI']):
        g=peer[peer.theme==theme]; ax.plot(g.fiscal_year,g.mentions_per_1000_words,marker='o',lw=2.5,color='#245978')
        ax.set(title=theme,xlabel='Fiscal year',ylabel='Mean mentions per 1,000 words'); ax.set_xticks(g.fiscal_year); ax.set_ylim(bottom=0); ax.grid(axis='y',alpha=.2)
    fig.suptitle('Risk Factors and MD&A language across eight insurers',fontsize=15,fontweight='bold')
    fig.tight_layout(); savefig(fig,out/'case3_peer_trends.png')
    fig,ax=plt.subplots(figsize=(11,6))
    for ticker,g in combined[combined.theme=='Technology and AI'].groupby('ticker'):
        ax.plot(g.fiscal_year,g.mentions_per_1000_words,marker='o',label=ticker)
    ax.set(title='Technology and AI language by insurer',xlabel='Fiscal year',ylabel='Mentions per 1,000 words in Item 1A and Item 7')
    ax.set_xticks(sorted(combined.fiscal_year.unique())); ax.set_ylim(bottom=0); ax.legend(ncol=4,loc='upper center',bbox_to_anchor=(.5,-.13)); ax.grid(axis='y',alpha=.2)
    savefig(fig,out/'case3_ai_by_company.png')

def run(args):
    for name in ['data','charts','sections']: (ROOT/name).mkdir(exist_ok=True)
    client=SECClient(args.cache,os.getenv('SEC_USER_AGENT',''),args.offline)
    companies=resolve_companies(client)
    (ROOT/'data'/'companies.json').write_text(json.dumps(companies,indent=2))
    filings={}; allfilings=[]; risks=[]; quality=[]
    for ticker,co in companies.items():
        print('Filing history',ticker,flush=True)
        filings[ticker]=select_filings(client,co['cik'],args.as_of,5)
        table=filings[ticker].copy(); table['ticker']=ticker; allfilings.append(table)
    pd.concat(allfilings).to_csv(ROOT/'data'/'filing_inventory.csv',index=False)
    if args.stage in ('all','finance'):
        base=financials(client,companies,filings,args.as_of,ROOT/'data')
        from filing_metrics import supplement_financials
        base=supplement_financials(client,pd.concat(allfilings),base,ROOT/'data')
        base.to_csv(ROOT/'data'/'financial_enriched_base.csv',index=False)
        fin,latest=derive_financials(base,ROOT/'data')
    if args.stage in ('all','text'):
        for ticker,table in filings.items():
            for _,filing in table.head(3).iterrows():
                print('Text',ticker,filing.reportDate,flush=True)
                html=client.get(filing.url); text=html_blocks(html)
                section_urls={'1A':filing.url,'7':filing.url}
                if ticker=='PGR':
                    sections=extract_sections(text,('1A',))
                    soup=BeautifulSoup(html,'lxml')
                    links=[x for x in soup.find_all('a') if 'Annual Report to Shareholders' in x.get_text()]
                    if len(links)!=1: raise ValueError('Ambiguous Progressive annual-report exhibit')
                    exhibit_url=urljoin(filing.url,links[0]['href'])
                    exhibit=html_blocks(client.get(exhibit_url))
                    start=re.search(r'Management[’\']s Discussion and Analysis of Financial Condition and Results of Operations',exhibit)
                    end=re.search(r'Safe Harbor Statement Under',exhibit[start.end():]) if start else None
                    if not start or not end: raise ValueError('Progressive MD&A exhibit boundaries missing')
                    finish=start.end()+end.start()
                    sections['7']={'text':exhibit[start.start():finish],'start_char':start.start(),'end_char':finish,'candidate_count':1}
                    section_urls['7']=exhibit_url
                else: sections=extract_sections(text)
                for section,detail in sections.items():
                    body=detail.pop('text'); year=int(filing.reportDate[:4])
                    (ROOT/'sections'/f'{ticker}_{year}_item{section}.txt').write_text(body,encoding='utf-8')
                    quality.append({'ticker':ticker,'fiscal_year':year,'section':section,'words':len(re.findall(r'\b\w+\b',body)),**detail,'url':section_urls[section]})
                    for r in count_themes(body): risks.append({'ticker':ticker,'company':COMPANIES[ticker],
                        'fiscal_year':year,'section':section,'accession':filing.accessionNumber,'url':section_urls[section],**r})
                pd.DataFrame(risks).to_csv(ROOT/'data'/'case3_section_theme_counts.csv',index=False)
                pd.DataFrame(quality).to_csv(ROOT/'data'/'section_quality.csv',index=False)
    manifest=[json.loads(p.read_text()) for p in client.cache.glob('*.json')]
    pd.DataFrame(manifest).drop_duplicates('url').to_csv(ROOT/'data'/'source_manifest.csv',index=False)
    if args.stage=='all':
        charts(fin,latest,pd.DataFrame(risks),ROOT/'charts')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',default=str(ROOT/'cache'))
    p.add_argument('--as-of',default='2026-10-21',help='Latest eligible filing date')
    p.add_argument('--offline',action='store_true')
    p.add_argument('--stage',choices=['all','finance','text'],default='all')
    run(p.parse_args())

