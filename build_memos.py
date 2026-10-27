"""Create the two one-page business memos for the delivered 2026-10-21 snapshot."""
from pathlib import Path
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
ROOT=Path(__file__).resolve().parent

CASE1=[
('lead','Progressive combines the strongest return on equity with the fastest premium growth. Everest merits the first follow-up review because weak profitability coincides with a shrinking premium base. These are screening conclusions for a business-intelligence review, not a normalized assessment of underwriting quality.'),
('bullet','Progressive leads both rankings: 40.4% ROE and 11.8% premium growth in 2025. Its 16.3% revenue growth places it at the upper right of the growth-versus-ROE chart, while its 87.4% combined ratio supports a profitable-underwriting interpretation.'),
('bullet','RenaissanceRe is the clearest profitability-growth divergence: 24.2% ROE ranks third, but premiums fell 0.8%, ranking seventh. Chubb shows the reverse relative pattern: second in premium growth at 6.6%, but seventh in ROE at 15.0%. Revenue growth at RenaissanceRe was positive, so the scatter alone would miss its premium contraction.'),
('bullet','Arch has the highest net profit margin, 22.1%, but ranks sixth in ROE at 19.5%. The margin chart therefore tells a different story from the ROE chart. Product mix, investment results, and capital intensity need to be separated before treating either measure as superior execution.'),
('bullet','Flag Everest: 10.8% ROE and a 1.9% premium decline rank last on both measures. Its derived combined ratio improved from 102.3% to 98.6%, but remains the highest in the peer set. Request a segment-level bridge of reserve development, catastrophe losses, pricing, and portfolio exits to test whether the recovery is sustainable.'),
('note','Basis: fiscal 2021-2025; latest ranking is 2025. ROE uses reported net income over average total stockholders\' equity. Premium and combined-ratio scopes differ across peers; Chubb includes life premiums and Arch includes mortgage insurance. Allstate\'s reported earnings include disposal gains. The CSV audits retain source facts and ratio components.')]

CASE3=[
('lead','Technology and AI language is growing fastest in percentage terms, while cyber has the largest absolute increase in normalized mentions. The useful business signal is where disclosure becomes more specific, not simply which company repeats a phrase most often.'),
('bullet','Across eight insurers, mean technology/AI mentions increased from 0.075 to 0.184 per 1,000 words between 2023 and 2025, up 144%. Cyber rose from 0.538 to 0.660, an absolute increase of 0.122 versus AI\'s 0.108. Catastrophe/climate fell slightly from 1.336 to 1.313, after peaking in 2024; this sample does not support a steady increase in that language.'),
('bullet','Travelers has the largest 2024-2025 increase in AI mention density: 0.274 to 0.517 per 1,000 words, up 89%. Raw mentions rose from 13 to 24, while the denominator fell only 2.2%, so shorter text alone does not explain the change. Arch moves from zero to three mentions, illustrating why low-base percentage comparisons are unreliable.'),
('bullet','The source text shows a more specific discussion of costs and regulation. Travelers\' 2025 Item 1A states: “Artificial intelligence, in particular, may become more expensive in the future given the resources necessary to develop that technology.” It also states: “Regarding artificial intelligence, legal and regulatory frameworks are developing and subject to change.” The evidence file compares these with a 2024 sentence about unforeseen coverage, fraud, and cyber exposure.'),
('body','Method and limits: count case-insensitive phrases in Item 1A and Item 7, normalize each company\'s combined sections by word count, then average companies equally. Progressive\'s MD&A is retrieved from its incorporated annual-report exhibit. Keyword counts miss synonyms and context and include boilerplate; more AI discussion does not establish adoption, materiality, or realized losses.'),
('body','Proposed LLM upgrade: align current and prior-year paragraphs, classify each mention as adoption, exposure, mitigation, or generic caution, and summarize the specific change with exact supporting quotes. Validate quotes against the filings, evaluate theme and change classifications on analyst-labeled pairs, and route material or uncertain results for human review. The accompanying design includes a prompt, schema, and evaluation plan; no LLM results are claimed.')]

def main():
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='MemoTitle',fontName='Helvetica-Bold',fontSize=19,leading=23,spaceAfter=8,textColor=colors.black))
    styles.add(ParagraphStyle(name='Meta',fontName='Helvetica',fontSize=9,leading=12,spaceAfter=12,textColor=colors.HexColor('#555555')))
    styles.add(ParagraphStyle(name='MemoBody',fontName='Helvetica',fontSize=10.2,leading=14.2,spaceAfter=9))
    styles.add(ParagraphStyle(name='MemoBullet',parent=styles['MemoBody'],leftIndent=12,firstLineIndent=-9))
    styles.add(ParagraphStyle(name='Note',fontName='Helvetica',fontSize=8.4,leading=11,spaceAfter=5,textColor=colors.HexColor('#444444')))
    story=[]
    titles=['Insurance peer benchmarking','Risk factor disclosure signals']
    markdown=[]
    for page,(title,content) in enumerate(zip(titles,[CASE1,CASE3])):
        if page: story.append(PageBreak())
        case=1 if page==0 else 3
        story.append(Paragraph(title,styles['MemoTitle']))
        story.append(Paragraph(f'Case study {case} | Business memo | 21 October 2026<br/>To the analytics hiring team | Prepared for Siddharth',styles['Meta']))
        markdown += [f'# {title}\n',f'Case study {case} | 21 October 2026\n']
        for kind,text in content:
            clean=text.replace('“','"').replace('”','"').replace('’',"'")
            prefix='- ' if kind=='bullet' else ''
            style=styles['MemoBullet' if kind=='bullet' else 'Note' if kind=='note' else 'MemoBody']
            story.append(Paragraph(escape(prefix+clean),style))
            markdown.append(prefix+clean+'\n')
        if page==0:
            latest=pd.read_csv(ROOT/'data/case1_latest_rankings.csv').sort_values('roe_pct_rank')
            table=[['2025 peer','ROE','ROE rank','Premium growth','Growth rank']]
            for _,r in latest.iterrows(): table.append([r.ticker,f'{r.roe_pct:.1f}%',str(int(r.roe_pct_rank)),f'{r.premium_growth_pct:.1f}%',str(int(r.premium_growth_pct_rank))])
            t=Table(table,colWidths=[95,80,80,120,90],hAlign='LEFT')
            t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8.5),
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eef2')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#d9d9d9')),
                ('ALIGN',(1,0),(-1,-1),'CENTER'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
            story.append(t)
        else:
            q=pd.read_csv(ROOT/'data/case3_sentence_evidence.csv')
            url=q[q.fiscal_year==2025].iloc[0].url
            story.append(Paragraph('Source for quoted sentences: <link href="'+url+'" color="#245978">Travelers fiscal 2025 Form 10-K, Item 1A</link>. All calculations and additional evidence are supplied in the project CSVs.',styles['Note']))
        story.append(Spacer(1,5))
    doc=SimpleDocTemplate(str(ROOT/'business_memos.pdf'),pagesize=(612,792),rightMargin=54,leftMargin=54,topMargin=43,bottomMargin=38,
                          title='Insurance peer benchmarking and risk factor disclosure signals',author='Siddharth')
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawString(54,23,'Technology and AI Analyst case studies');canvas.drawRightString(558,23,str(doc.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    (ROOT/'business_memos.md').write_text('\n'.join(markdown),encoding='utf-8')

if __name__=='__main__': main()
