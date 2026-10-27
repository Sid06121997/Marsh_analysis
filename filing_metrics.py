"""Extract auditable numeric inline-XBRL facts from primary 10-K HTML."""
import re
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def inline_facts(html):
    soup=BeautifulSoup(html,'lxml')
    contexts={}
    for c in soup.find_all(lambda x:x.name and x.name.lower().endswith(':context')):
        def text(local):
            e=c.find(lambda x:x.name and x.name.lower().split(':')[-1]==local)
            return e.get_text(strip=True) if e else ''
        dimensions=';'.join(x.get('dimension','')+'='+x.get_text(strip=True) for x in c.find_all(lambda x:x.name and x.name.lower().endswith(':explicitmember')))
        contexts[c.get('id')]={'start':text('startdate'),'end':text('enddate') or text('instant'),'dimensions':dimensions}
    rows=[]
    for x in soup.find_all('ix:nonfraction'):
        context=contexts.get(x.get('contextref'),{})
        raw=x.get_text('',strip=True).replace(',','').replace('−','-').replace('–','-')
        if raw in ('','—','-'): value=0.0 if raw else None
        else:
            try: value=float(raw.replace('(','-').replace(')',''))
            except ValueError: continue
        if value is not None:
            value*=10**int(x.get('scale','0'))
            if x.get('sign')=='-': value=-abs(value)
        rows.append({'tag':x.get('name'),'value':value,'unit':x.get('unitref'),**context})
    return pd.DataFrame(rows).drop_duplicates()

def supplement_financials(client,inventory,base,out):
    """Use 2025 and 2022 10-K comparative tables to cover the six-year base.
    Select explicit consolidated underwriting tables; do not mix segment ratios.
    """
    audit=[]; fills=[]
    patterns={
      'TRV': [r'^Loss and loss adjustment expense ratio',r'^Underwriting expense ratio',r'^Combined ratio'],
      'CB': [r'^Loss and loss expense ratio',r'^Policy acquisition cost ratio',r'^Administrative expense ratio',r'^P&C Combined ratio'],
      'ALL':[r'^Loss ratio',r'^Expense ratio',r'^Combined ratio'],
      'EG':[r'^Loss ratio',r'^Commission and brokerage ratio',r'^Other underwriting expense ratio',r'^Combined ratio'],
      'PGR':[r'^Loss & loss adjustment expense ratio',r'^Underwriting expense ratio',r'^Combined ratio'],
      'WRB':[r'^Loss ratio',r'^Expense ratio',r'^Combined ratio'],
      'RNR':[r'^Net claims and claim expense ratio',r'^Underwriting expense ratio',r'^Combined ratio']}
    for ticker,group in inventory.groupby('ticker',sort=False):
        for pos in [0,3]:
            filing=group.iloc[pos];url=filing.url
            html=client.get(url);soup=BeautifulSoup(html,'lxml')
            if ticker=='PGR':
                link=next(x for x in soup.find_all('a') if 'Annual Report to Shareholders' in x.get_text())
                url=urljoin(url,link['href']);html=client.get(url);soup=BeautifulSoup(html,'lxml')
            if ticker in ('ALL','ACGL','RNR'):
                inline=inline_facts(html)
                annual=inline[inline.start.fillna('').str.endswith('01-01') & inline.end.fillna('').str.endswith('12-31')].copy()
                if ticker=='ALL':
                    selected=annual[(annual.tag=='us-gaap:PremiumsWrittenNet') & annual.dimensions.str.contains('PropertyLiabilityAndCasualtyInsuranceSegmentMember',na=False)]
                    for _,r in selected.iterrows():
                        fills.append({'ticker':ticker,'period_end':r.end,'metric':'net_written_premiums','value':r.value,'url':url,'filed':filing.filingDate,'tag':r.tag,'scope':r.dimensions})
                else:
                    annual=annual[annual.dimensions=='']
                    names=(['us-gaap:LossRatio','us-gaap:AcquisitionCostRatio','acgl:OtherOperatingExpenseNetRatioPercentage','acgl:CombinedRatioPercentage'] if ticker=='ACGL' else ['us-gaap:LossRatio','us-gaap:UnderwritingExpenseRatio','us-gaap:CombinedRatio'])
                    for end,g in annual.groupby('end'):
                        found=[]
                        for tag in names:
                            vals=g[g.tag==tag].value.dropna().unique()
                            if len(vals)==0 and tag=='us-gaap:AcquisitionCostRatio':
                                vals=g[g.tag=='acgl:AcquisitionExpenseRatioPercentage'].value.dropna().unique()
                            if len(vals)==0 and tag=='acgl:OtherOperatingExpenseNetRatioPercentage':
                                vals=g[g.tag=='acgl:OtherOperatingExpenseRatioPercentage'].value.dropna().unique()
                            if len(vals)!=1: break
                            found.append(float(vals[0])*100)
                        if len(found)==len(names):
                            audit.append({'ticker':ticker,'period_end':end,'loss_ratio_pct':found[0],
                                'expense_ratio_pct':sum(found[1:-1]),'derived_combined_ratio_pct':sum(found[:-1]),
                                'reported_combined_ratio_pct':found[-1],'url':url,'filed':filing.filingDate,
                                'source_rows':' + '.join(names),'scope':('Insurance, reinsurance and mortgage; excludes corporate and other' if ticker=='ACGL' else 'Consolidated underwriting operations')})
                    continue
            pats=patterns[ticker];selected=None
            for table in soup.find_all('table'):
                rows=[tr.get_text(' ',strip=True) for tr in table.find_all('tr')]
                matches=[[r for r in rows if re.match(p,r,re.I) and len(re.findall(r'(?<!\d)\d+\.\d+',r))>=2] for p in pats]
                if not all(matches): continue
                text=table.get_text(' ',strip=True)
                years=re.findall(r'\b20\d{2}\b',text)
                if str(filing.reportDate)[:4] not in years[:12]: continue
                if ticker=='PGR' and 'Total Underwriting Operations' not in text: continue
                selected=(table,matches);break
            if selected is None and ticker=='EG':
                # The 2022 filing renders its tables with positioned div elements.
                text=re.sub(r'\s+',' ',soup.get_text(' ',strip=True))
                chosen=[]
                for pattern in pats:
                    match=re.search(pattern.lstrip('^')+r'\s+((?:\d+\.\d+\s*%?\s*){3})',text,re.I)
                    if not match: raise ValueError('Everest div-table ratio not found')
                    chosen.append(match.group())
            else:
                if selected is None: raise ValueError(f'No auditable ratio table: {ticker} {filing.reportDate}')
                table,matches=selected
                # WRB and PGR list segments before consolidated totals within the same table.
                chosen=[m[-1] if ticker in ('PGR','WRB') else m[0] for m in matches]
            values=[[float(x) for x in re.findall(r'(?<!\d)\d+\.\d+',r)] for r in chosen]
            endyear=int(filing.reportDate[:4]); count=min(3,min(map(len,values)))
            for i in range(count):
                parts=[v[i] for v in values]
                audit.append({'ticker':ticker,'period_end':f'{endyear-i}-12-31',
                    'loss_ratio_pct':parts[0],'expense_ratio_pct':sum(parts[1:-1]),
                    'derived_combined_ratio_pct':sum(parts[:-1]),'reported_combined_ratio_pct':parts[-1],
                    'url':url,'filed':filing.filingDate,'source_rows':' | '.join(chosen),
                    'scope':{'CB':'P&C only; excludes life','ALL':'Property-Liability; excludes Protection Services'}.get(ticker,'Consolidated underwriting operations')})
    ratios=pd.DataFrame(audit).sort_values('filed').drop_duplicates(['ticker','period_end'],keep='last')
    ratios['rounding_difference_pp']=ratios.derived_combined_ratio_pct-ratios.reported_combined_ratio_pct
    if (ratios.rounding_difference_pp.abs()>.21).any():
        raise ValueError('Combined-ratio components do not reconcile: '+ratios[ratios.rounding_difference_pp.abs()>.21].to_string())
    ratios.to_csv(out/'combined_ratio_audit.csv',index=False)
    fills=pd.DataFrame(fills).sort_values('filed').drop_duplicates(['ticker','period_end','metric'],keep='last')
    fills.to_csv(out/'supplemental_fact_audit.csv',index=False)
    for _,r in fills.iterrows(): base.loc[(base.ticker==r.ticker)&(base.period_end==r.period_end),r.metric]=r.value
    base=base.merge(ratios[['ticker','period_end','derived_combined_ratio_pct','scope']],on=['ticker','period_end'],how='left')
    base=base.rename(columns={'derived_combined_ratio_pct':'combined_ratio_pct','scope':'combined_ratio_scope'})
    base['premium_scope']=base.ticker.map({'ALL':'P&C including Protection Services','CB':'Consolidated including life','ACGL':'Consolidated including mortgage'}).fillna('Consolidated')
    return base
