from pathlib import Path
from datetime import date
from io import BytesIO
import calendar
import os
import html
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from bosch_bi.schemas import SCHEMAS, BUS, recognize, suggest_mapping, template
from bosch_bi.storage import Store, validate
from bosch_bi.transfer import export_workspace,read_workspace,import_workspace,decrypt_workspace
from bosch_bi.adapters import adapter_kind,parse_source,period_from_filename
from bosch_bi.policy import FX_POLICY,fixed_rate
from bosch_bi.demo import generate
from bosch_bi.engine import divide,growth,pp,total,weighted_rate,exact_audience,convert,previous_month,previous_year_period,comparable_dates,ranked_products,opportunity,complete_scopes,complete_months,reconciliation,product_store_reconciliation
from bosch_bi.charts import plot,combo,donut,BLUE,TEAL,NAVY,RED
from bosch_bi.presentation import number,numeric_display,numeric_columns,marketplace_theme,MARKETPLACE_COLORS

st.set_page_config(page_title='Bosch | Commerce Intelligence',page_icon='📊',layout='wide',initial_sidebar_state='expanded')
from bosch_bi.security import require_access
require_access()
st.markdown('''<style>

.block-container{padding:1.6rem 2.4rem 3rem;max-width:1800px}h1,h2,h3{letter-spacing:-.035em}h1{font-size:2rem!important;font-weight:700!important}h2{font-size:1.25rem!important}h3{font-size:1rem!important}
[data-testid="stSidebar"]{background:#123047}[data-testid="stSidebar"] *{color:#E8F0F5}[data-testid="stSidebar"] [data-baseweb="select"] *{color:#183047}[data-testid="stSidebar"] hr{border-color:#ffffff25}
[data-testid="stSidebar"] [role="radiogroup"]{gap:.55rem}[data-testid="stSidebar"] [role="radio"]{accent-color:#56C0F3}
[data-testid="stMetric"]{background:#fff;border:1px solid #E2E8EF;border-radius:10px;padding:18px 18px 15px;box-shadow:0 3px 8px #152E4304}[data-testid="stMetricLabel"]{color:#607487;font-size:.8rem}[data-testid="stMetricValue"]{font-size:1.65rem;font-weight:650;color:#173B57}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-color:#E4EAF0!important;border-radius:10px!important;background:#fff}
.marketplace-heading{border-left:4px solid;padding:5px 14px;margin:4px 0 16px;background:linear-gradient(90deg,#f8fafc,transparent);border-radius:4px}.marketplace-heading>span{font-size:.68rem;letter-spacing:.12em;font-weight:800}.marketplace-heading h3{margin:4px 0}.report-banner{display:flex;align-items:center;gap:18px;padding:14px 18px;margin:12px 0;border-radius:10px;background:#fff;border:1px solid #e2e8ef}.bosch-banner{border-left:5px solid #e20015;background:linear-gradient(100deg,#fff4f4,#fff 45%,#eef7fc)}.bosch-banner b{color:#e20015;letter-spacing:.08em}.bosch-banner span{font-size:.85rem;color:#536779}.eyebrow{font-size:.71rem;font-weight:700;letter-spacing:.15em;color:#74899A;text-transform:uppercase}.brand{font-size:2.15rem;font-weight:800;letter-spacing:.035em;color:#ED1C24!important}.brand-sub{font-size:.68rem;letter-spacing:.16em;color:#99B2C5!important}.section-rule{height:4px;background:linear-gradient(90deg,#E20015 0 19%,#B51455 19% 35%,#654A92 35% 50%,#007BC0 50% 70%,#00A4B4 70% 85%,#76B82A 85%);border-radius:2px;margin-bottom:20px}.demo-pill{display:inline-block;padding:5px 10px;border:1px solid #E9D9A1;color:#8D6913;background:#FFFAE9;font-size:.72rem;border-radius:5px;font-weight:650}.subtle{color:#6A7F90;font-size:.88rem}.card-note{font-size:.72rem;color:#718497;margin:5px 1px 12px}.stDownloadButton button{font-size:.78rem}div[data-testid="stTabs"] button{font-size:.86rem}
</style>''',unsafe_allow_html=True)

@st.cache_data
def demo_frames():return generate()

@st.cache_resource
def database(path):return Store(path)

def fmt(v,kind='number',currency=None):
    if v is None or pd.isna(v):return '—'
    places=st.session_state.get('decimal_places',2)
    if kind=='pct':return number(v,places)+'%'
    if kind=='pp':return number(v,places,True)+' pp'
    if kind=='money':return f'{currency or report_currency} '+number(v,places)
    return number(v,places)

def caption(text):st.markdown(f'<div class="subtle">{html.escape(text)}</div>',unsafe_allow_html=True)

def section(title,note=None):
    platform=next((p for p in MARKETPLACE_COLORS if p.lower() in title.lower()),None)
    if platform:
        accent=MARKETPLACE_COLORS[platform]
        st.markdown(f'<div class="marketplace-heading" style="border-left-color:{accent}"><span style="color:{accent}">{platform.upper()}</span><h3>{html.escape(title)}</h3></div>',unsafe_allow_html=True)
    else:st.subheader(title)
    if note:st.caption(note)

def table(df,key,changes=()):
    if df.empty:st.info('No records for this selection.');return
    def color(v):
        if not isinstance(v,(int,float)) or pd.isna(v):return ''
        return 'color: #147D64; background-color: #EAF7F2' if v>=0 else 'color: #C53545; background-color: #FFF0F1'
    labels={'canonical_sku':'Reporting SKU / listing ID','previous_rank':'Previous rank','rank_movement':'Rank movement','gm_pct':'GM %','share':'Revenue share %','cr':'Buyer CR %','asp':'ASP','atc_units':'Add-to-cart units','share_pp':'Share Δ pp','cr_pp':'CR Δ pp','is_bundle':'Bundle','revenue_change':'Revenue Δ %','units_change':'Units Δ %','visitors_change':'Visitors Δ %','buyers_change':'Buyers Δ %','atc_units_change':'ATC Δ %','asp_change':'ASP Δ %'}
    display=numeric_display(df).rename(columns={c:labels.get(c,c.replace('_',' ').capitalize() if c.islower() or '_' in c else c) for c in df.columns})
    signed=[labels.get(c,c.replace('_',' ').capitalize() if c.islower() or '_' in c else c) for c in changes if c in df]
    places=st.session_state.get('decimal_places',2)
    numeric=numeric_columns(display)
    styled=display.style.map(color,subset=signed).format({c:lambda v,c=c:number(v,places,c in signed) for c in numeric},na_rep='—')
    config={}
    for original,shown in zip(df.columns,display.columns):
        if shown in numeric:
            config[shown]=st.column_config.NumberColumn(format=('%+' if shown in signed else '%')+f'.{places}f')
    st.dataframe(styled,width='stretch',hide_index=True,column_config=config)
    # Escape spreadsheet formulas in textual cells before exporting CSV.
    safe=df.copy()
    for c in safe.select_dtypes(include=['object','string']).columns:
        safe[c]=safe[c].map(lambda v:"'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v)
    st.download_button('↓ Download table · CSV',safe.to_csv(index=False).encode(),f'{key}.csv','text/csv',key='dl_'+key)

def metric_row(items):
    cols=st.columns(len(items))
    for col,item in zip(cols,items):
        with col:st.metric(item[0],item[1],item[2] if len(item)>2 else None)

path=os.environ.get('BOSCH_BI_DB',str(Path(__file__).parent/'data'/'reporting.sqlite'))
store=database(path)
has_uploaded_data=not store.read('financial_actuals').empty or not store.read('marketplace').empty
NAV=['Executive overview','Financial performance','Marketplace performance','Product & SKU','Conversion analysis','Advertising performance','BRM workbook','Data workspace','Reporting methodology']
def reset_chart_labels():
    st.session_state['chart_label_preferences']={}
    for k in list(st.session_state):
        if k.startswith('chart_labels_'):del st.session_state[k]
with st.sidebar:
    st.markdown('<div class="brand">BOSCH</div><div class="brand-sub">POWER TOOLS · COMMERCE INTELLIGENCE</div>',unsafe_allow_html=True)
    st.write('');st.divider()
    page=st.radio('WORKSPACE',NAV,label_visibility='visible')
    st.divider()
    mode=st.radio('Data source',['Demo workspace','Uploaded data'],index=1 if has_uploaded_data else 0,key='source_mode')
    with st.expander('Display settings',expanded=True):
        st.selectbox('Decimals',[0,2],index=1,format_func=lambda v:'No decimals' if v==0 else '2 decimals',key='decimal_places',help='Applies to KPI cards, tables, chart values, axes and tooltips. Source values are unchanged.')
        st.toggle('Labels on all charts',key='default_chart_labels',on_change=reset_chart_labels,help='Set the default for all charts. Each chart also has its own Data labels switch.')
    st.caption('Malaysia\n\nShopee · Lazada')
    st.write('');st.caption('MONTHLY BUSINESS REVIEW\n\nFinance · Commerce · Growth')

frames=demo_frames() if mode=='Demo workspace' else {k:store.read(k) for k in SCHEMAS}

st.markdown('<div class="section-rule"></div>',unsafe_allow_html=True)
head,badge=st.columns([5,1.5])
with head:
    st.markdown('<div class="eyebrow">E-COMMERCE INTELLIGENCE / MANAGEMENT REPORTING</div>',unsafe_allow_html=True)
    st.title(page)
    if page=='Executive overview':
        st.markdown('<div class="report-banner bosch-banner"><b>BOSCH</b><span>Malaysia · Business review</span></div>',unsafe_allow_html=True)
with badge:
    st.write('')
    if mode=='Demo workspace':st.markdown('<span class="demo-pill">● SYNTHETIC DEMO DATA</span>',unsafe_allow_html=True)
    else:st.success('Uploaded data only',icon='🔒')
caption('A connected view of sales, profitability and marketplace growth.')
st.write('')
filters=st.columns([1,1,1,1,1,1.3])
with filters[0]:country_label=st.selectbox('Country',['Malaysia'],key='country')
with filters[1]:marketplace=st.selectbox('Marketplace',['All marketplaces','Shopee','Lazada'],key='marketplace')
available_years=set(range(2020,2027))
for data in frames.values():
    for field in ['period','period_start']:
        if field in data:
            available_years.update(pd.to_datetime(data[field],errors='coerce').dropna().dt.year.tolist())
with filters[2]:year=st.selectbox('Year',sorted(available_years,reverse=True),index=sorted(available_years,reverse=True).index(2026),key='year')
with filters[3]:month=st.selectbox('Through month',list(range(1,13)),index=8,format_func=lambda x:calendar.month_abbr[x],key='month')
with filters[4]:report_currency=st.selectbox('Currency',['EUR','MYR','SGD'],key='currency')
with filters[5]:period_mode=st.selectbox('Reporting period',['Year to date','Selected month','Custom month range'],key='period_mode')
end=date(year,month,calendar.monthrange(year,month)[1]);start=date(year,1 if period_mode=='Year to date' else month,1)
with st.expander('Advanced filters · dates, product scope & exchange rates'):
    c1,c2,c3=st.columns(3)
    with c1:
        selected_dates=st.date_input('Date range',value=(start,end),key=f'dates_{year}_{month}_{period_mode}',disabled=period_mode!='Custom month range')
    with c2:bu=st.multiselect('Business unit · product views only',BUS,key='bu')
    with c3:
        order_basis=st.selectbox('Shopee order basis',['Confirmed Order'],key='order_basis')
        methods=sorted(frames['fx'].methodology.dropna().unique())
        fx_method=st.selectbox('FX methodology',methods or [FX_POLICY],key='fx_method')
    m=frames['sku_master']
    c1,c2=st.columns(2)
    with c1:groups=st.multiselect('Product group · product views only',sorted(m.product_group.dropna().unique()),key='groups')
    listing_ids=frames['listing_products'][['country','marketplace','listing_sku']].drop_duplicates()
    listing_options=(listing_ids.country+':'+listing_ids.marketplace+':'+listing_ids.listing_sku).tolist() if not listing_ids.empty else []
    with c2:skus=st.multiselect('Canonical SKU / listing ID · product views only',sorted(set(m.canonical_sku.dropna().unique())|set(listing_options)),key='skus')
if period_mode=='Custom month range':
    if len(selected_dates)!=2:st.info('Select a start and end date.');st.stop()
    start,end=selected_dates
    if start.day!=1 or end.day!=calendar.monthrange(end.year,end.month)[1] or start.year!=end.year:
        st.warning('Monthly modules use complete monthly reports; daily records are available in Marketplace performance. Select a range starting on day 1, ending on month-end, within the selected year. Use the daily tab for a shorter date range.');st.stop()
    if start.year!=year:st.warning('The date range must match the selected year.');st.stop()
    month=end.month
current=f'{year}-{month:02d}';previous=previous_month(current)
st.caption(FX_POLICY+' · MYR → EUR divides by 4.64. Other currency pairs require approved FX imports.')
caption(f'{start:%d %b %Y} — {end:%d %b %Y}  ·  {country_label}  /  {marketplace}  ·  Reporting in {report_currency}')
if mode=='Demo workspace':st.caption('All operating figures, forecasts, product identities and other-currency exchange rates below are synthetic; EUR/MYR follows the fixed Bosch policy. Uploads never modify this demonstration.')
if bu or groups or skus:st.caption('Product filters apply to Product & SKU and Conversion analysis. Finance, shop totals and advertising retain the store scope.')

country={'Malaysia':'MY','Singapore':'SG'}.get(country_label)
def scoped(df):
    x=df.copy()
    if country and 'country' in x:x=x[x.country==country]
    if marketplace!='All marketplaces' and 'marketplace' in x:x=x[x.marketplace==marketplace]
    return x

def basis_filter(df):
    if 'sales_basis' not in df:return df
    return df[(df.marketplace!='Shopee')|(df.sales_basis==order_basis)]

def monthly(df,a=start,b=end):
    if df.empty:return df
    return df[(df.period>=str(a)[:7]) & (df.period<=str(b)[:7])]

scope_grid=[(c,p) for c in ([country] if country else ['MY','SG']) for p in ([marketplace] if marketplace!='All marketplaces' else ['Shopee','Lazada'])]
finance_scope_grid=[]
for c in ([country] if country else ['MY','SG']):
    has_consolidated=any(not data[(data.country==c)&(data.marketplace=='Consolidated')].empty for data in [frames['financial_actuals'],frames['forecasts']])
    finance_scope_grid.extend([(c,'Consolidated')] if marketplace=='All marketplaces' and has_consolidated else [(c,p) for p in ([marketplace] if marketplace!='All marketplaces' else ['Shopee','Lazada'])])
def finance_scope(df):
    return df[df.apply(lambda r:(r.country,r.marketplace) in finance_scope_grid,axis=1)] if not df.empty else df
if page in ['Executive overview','Financial performance'] and any(p=='Consolidated' for _,p in finance_scope_grid):
    st.caption('Finance scope: country consolidated TNS. It is never allocated to individual marketplaces or added to marketplace-level finance totals.')
def money_frame(key,fields):
    source=finance_scope(frames[key]).copy() if key=='financial_actuals' else basis_filter(scoped(frames[key]))
    if key=='financial_actuals' and not frames['financial_rates'].empty:
        rates=frames['financial_rates'][['country','marketplace','period','gm_pct']].rename(columns={'gm_pct':'reported_gm'})
        source=source.merge(rates,on=['country','marketplace','period'],how='left',validate='one_to_one')
        source['gm_pct']=source['gm_pct'].where(source['gm_pct'].notna(),source['reported_gm'])
        source=source.drop(columns='reported_gm')
    x=convert(source,fields,report_currency,frames['fx'],fx_method)
    if key in ['financial_actuals','marketplace']:
        periods=[f'{y}-{m:02d}' for y in [year-1,year] for m in range(1,13)]
        x=complete_months(x,finance_scope_grid if key=='financial_actuals' else scope_grid,periods)
    return x
fin=money_frame('financial_actuals',['tns','gm_basis','concession_basis'])
shop=money_frame('marketplace',['gmv'])
products=money_frame('products',['revenue','gm_basis'])
ads=money_frame('ads',['spend','ads_gmv'])
traffic=basis_filter(scoped(frames['traffic']))
forecasts=finance_scope(frames['forecasts']).copy()
# Monthly FX applies only to complete single-month forecast intervals. Annual targets
# need to be supplied in the selected reporting currency; never guess an annual rate.
if not forecasts.empty:
    forecasts['period']=forecasts.period_start.str[:7]
    original=forecasts.copy()
    forecasts=convert(forecasts,['tns','gm_basis','concession_basis'],report_currency,frames['fx'],fx_method)
    annual=original.period_start.str[:7]!=original.period_end.str[:7]
    unavailable=annual & original.currency.map(lambda source:fixed_rate(source,report_currency) is None)
    forecasts.loc[unavailable,['tns','gm_basis','concession_basis']]=float('nan')
    forecasts.loc[unavailable,'fx_missing']=True
for label,x in [('Finance',fin),('Marketplace',shop),('Products',products),('Advertising',ads),('Forecasts',forecasts)]:
    if 'fx_missing' in x and x.fx_missing.any():st.warning(f'{label}: some amounts are unavailable because the selected FX rate is missing. Annual targets require the reporting currency or the fixed EUR/MYR policy.')

if page in ['Executive overview','Financial performance']:
    missing=monthly(fin).tns.isna().sum()
    if missing:st.info(f'Finance coverage: {missing} selected store-month amounts are unavailable. Totals requiring those records remain blank. Import financial actuals and any required FX rates.')
months=[f'{year}-{i:02d}' for i in range(1,13)]

def financial_months():
    rows=[]
    for p in months:
        f=fin[fin.period==p];ly=fin[fin.period==previous_year_period(p)];prev=fin[fin.period==previous_month(p)]
        fc=forecasts[(forecasts.period_start.str[:7]==p) & (forecasts.period_end.str[:7]==p)] if not forecasts.empty else forecasts
        actual=total(f,'tns');off=total(complete_scopes(fc[fc.scenario=='official'],finance_scope_grid),'tns');stretch=total(complete_scopes(fc[fc.scenario=='stretch'],finance_scope_grid),'tns')
        rows.append({'Month':calendar.month_abbr[int(p[-2:])],'Previous year':total(ly,'tns'),'Current year':actual,'Official forecast':off,'Stretch forecast':stretch,'YoY %':growth(actual,total(ly,'tns')),'MoM %':growth(actual,total(prev,'tns')),'Attainment %':divide(actual,off,100),'Variance':pp(actual,off)})
    return pd.DataFrame(rows)

def with_benchmark(frame,a,b,scenario):
    benchmarks=finance_scope(frames['kpi_benchmarks'])
    out=[]
    for c,p in finance_scope_grid:
        x=frame[(frame.country==c)&(frame.marketplace==p)]
        bmark=benchmarks[(benchmarks.country==c)&(benchmarks.marketplace==p)&(benchmarks.period_start==str(a))&(benchmarks.period_end==str(b))&(benchmarks.scenario==scenario)]
        if len(bmark)==1:
            record={field:None for field in frame.columns}
            record.update(bmark.iloc[0].dropna().to_dict());record['tns']=total(x,'tns')
            out.append(pd.DataFrame([record]))
        else:out.append(x)
    return pd.concat(out,ignore_index=True) if out else frame

def exact_forecast(a,b,scenario):
    chunks=[]
    for c,p in finance_scope_grid:
        base=forecasts[(forecasts.country==c)&(forecasts.marketplace==p)&(forecasts.scenario==scenario)]
        exact=base[(base.period_start==str(a))&(base.period_end==str(b))]
        if not exact.empty:chunks.append(exact);continue
        parts=[]
        for period in pd.period_range(a,b,freq='M').astype(str):
            x=base[(base.period_start.str[:7]==period)&(base.period_end.str[:7]==period)]
            parts.append(complete_scopes(x,[(c,p)]))
        if parts:chunks.append(pd.concat(parts,ignore_index=True))
    result=pd.concat(chunks,ignore_index=True) if chunks else forecasts.iloc[:0]
    return with_benchmark(result,a,b,scenario)

def annual_target():
    x=forecasts[(forecasts.scenario=='target') & (forecasts.period_start==f'{year}-01-01') & (forecasts.period_end==f'{year}-12-31')]
    return with_benchmark(complete_scopes(x,finance_scope_grid),date(year,1,1),date(year,12,31),'target')

def finance_chart(key):
    df=financial_months().set_index('Month')
    plot(combo(df,['Current year','Previous year'],['Official forecast','Stretch forecast'],report_currency,marketplace='Bosch'),key,350)

if page=='BRM workbook':
    st.caption('The five BRM tabs share a common reporting foundation. Other workbook tabs are excluded. Internal TNS takes priority; raw 2026 shop exports take priority over manual tracking.')
    names=['Monthly Tracking','BICOS','Sales & Traffic Shopee','Sales & Traffic Shopee Lazada','Ads 2026']
    tabs=st.tabs(names)
    reference=scoped(frames['brm_tracking'])
    checks=frames['brm_review']
    with tabs[0]:
        section('Monthly Tracking · source history and reconciliation')
        st.info('2025 tracker history is retained. Shopee historical order status is unverified; it is not treated as Confirmed. 2026 manual tracking mixes order bases, so the raw Confirmed Order exports remain primary.')
        table(reference,'brm_tracking_reference')
        comparison=[]
        for _,r in reference.iterrows():
            if not str(r.period).startswith(str(year)):continue
            x=shop[(shop.country==r.country)&(shop.marketplace==r.marketplace)&(shop.period==r.period)]
            expected=total(x,'gmv');value=convert(pd.DataFrame([r]),['gmv'],report_currency,frames['fx'],fx_method).gmv.iloc[0]
            comparison.append({'Month':r.period,'Marketplace':r.marketplace,'Manual tracking':value,'Raw selected basis':expected,'Difference':pp(value,expected)})
        table(pd.DataFrame(comparison),'brm_tracking_comparison',['Difference'])
    with tabs[1]:
        section('BICOS · corrected TNS source')
        st.info('2025 and earlier BICOS values are excluded. TNS uses the internal Bosch workbook. Monthly 2026 GM% is retained; the workbook’s arithmetic-average YTD GM is shown for review, not used as a weighted rate.')
        finance_chart('brm_tns')
        table(fin[fin.period.str.startswith(str(year))][['period','tns','gm_pct']],'brm_finance_monthly')
        table(checks[checks.tab=='BICOS'],'brm_bicos_review')
        differences=[]
        internal=scoped(frames['financial_actuals'])
        for _,r in checks[checks.metric=='BICOS TNS reference'].iterrows():
            source=internal[(internal.marketplace=='Consolidated')&(internal.period==r.period)&(internal.currency=='EUR')]
            actual=total(source,'tns')
            differences.append({'Month':r.period,'BICOS EUR reference':r.value,'Internal EUR actual':actual,'Difference EUR':pp(r.value,actual)})
        table(pd.DataFrame(differences),'brm_tns_reconciliation',['Difference EUR'])
    for tab,platform in zip(tabs[2:4],['Shopee','Lazada']):
        with tab:
            section(platform+' · raw current year and tracker history')
            data=[]
            for m in range(1,13):
                old=reference[(reference.marketplace==platform)&(reference.period==f'{year-1}-{m:02d}')]
                if not old.empty:old=convert(old,['gmv'],report_currency,frames['fx'],fx_method)
                current_shop=shop[(shop.marketplace==platform)&(shop.period==f'{year}-{m:02d}')]
                data.append({'Month':calendar.month_abbr[m],'Prior tracker GMV':total(old,'gmv'),'Current raw GMV':total(current_shop,'gmv')})
            if platform=='Shopee':st.warning('Prior-year Shopee order status is unverified. Bars are a reference comparison; Confirmed-only YoY is unavailable until the historical basis is established.')
            chart=pd.DataFrame(data);plot(combo(chart.set_index('Month'),['Prior tracker GMV','Current raw GMV'],[],report_currency,marketplace=platform),'brm_market_'+platform)
            table(chart,'brm_market_'+platform)
    with tabs[4]:
        section('Ads 2026 · source-reported investment')
        st.warning('The workbook’s store-GMV denominators reference 2025 tracking rows. They are excluded from 2026 ratios. Ad attribution and order status are still unverified; reported ROAS is separate from Confirmed Order shop reporting.')
        x=monthly(ads).copy()
        x['Reported ROAS']=x.apply(lambda r:divide(r.ads_gmv,r.spend),axis=1)
        table(x.drop(columns='fx_missing',errors='ignore'),'brm_ads_reported')
        table(checks[checks.tab=='Ads 2026'],'brm_ads_formula_review')

elif page=='Executive overview':
    now=monthly(fin);a,b=comparable_dates(start,end);ly=monthly(fin,a,b)
    audience=exact_audience(traffic,start,end);aud_ly=exact_audience(traffic,a,b)
    fc=exact_forecast(start,end,'official');target=annual_target()
    def measure(frame,uv=None,buyers=None):
        tns=total(frame,'tns');orders=total(frame,'orders')
        return [tns,weighted_rate(frame,'gm_pct','gm_basis'),uv,buyers,divide(buyers,uv,100),orders,divide(tns,orders),weighted_rate(frame,'return_rate','return_basis'),weighted_rate(frame,'cost_concession_pct','concession_basis')]
    def forecast_measure(x):
        u,v=exact_audience(x,start,end) if not x.empty else (None,None)
        return measure(x,u,v)
    actuals=measure(now,*audience);last=measure(ly,*aud_ly);expected=forecast_measure(fc)
    if mode=='Uploaded data' and all(actuals[i] is None for i in [1,5,7,8]):st.caption('The supplied finance source covers TNS. Profitability rates and finance-order measures need an additional approved finance export.')
    ta_u,ta_b=exact_audience(target,date(year,1,1),date(year,12,31)) if not target.empty else (None,None)
    targets=measure(target,ta_u,ta_b)
    names=['TNS / Net sales','Gross margin','Unique visitors','Unique buyers','Conversion rate','Orders','AOV · TNS','Return rate','Cost concession']
    kinds=['money','pct','number','number','pct','number','money','pct','pct']
    ratios={1,4,7,8};lower={7,8};matrix=[]
    for offset in range(0,9,3):
        cols=st.columns(3)
        for col,i in zip(cols,range(offset,min(offset+3,9))):
            value=actuals[i];prior=last[i];comparison=expected[i]
            delta=pp(value,prior) if i in ratios else growth(value,prior)
            label=None if delta is None else (fmt(delta,'pp') if i in ratios else number(delta,st.session_state['decimal_places'],True)+'% YoY')
            with col:
                st.metric(names[i]+(' · EUR' if i==0 and report_currency=='EUR' else ''),fmt(value,kinds[i]),label,delta_color='inverse' if i in lower else 'normal')
                st.caption(f'PY: {fmt(prior,kinds[i])}  ·  Forecast: {fmt(comparison,kinds[i])}  ·  Δ: {fmt(pp(value,comparison),"pp" if i in ratios else kinds[i])}');st.caption(f'Forecast attainment: {fmt(divide(value,comparison,100),"pct")}  ·  FY target: {fmt(targets[i],kinds[i])}')
            matrix.append({'KPI':names[i],'Unit':'%' if i in ratios else (report_currency if kinds[i]=='money' else 'count'),'PY comparable actual':prior,'Full-year target':targets[i],'Current actual':value,'Period forecast':comparison,'YoY %':growth(value,prior),'YoY pp':pp(value,prior) if i in ratios else None,'Forecast attainment %':divide(value,comparison,100),'Forecast variance':pp(value,comparison),'YoY absolute variance':pp(value,prior),'Annual target achieved %':divide(value,targets[i],100) if i not in ratios else None})
    if audience[0] is None:st.info('Unique visitors, unique buyers and CR require one store’s deduplicated export covering this exact interval. They are unavailable for consolidated stores or when only monthly audience reports exist.')
    left,right=st.columns([2.2,1])
    with left:
        with st.container(border=True):section('Revenue trajectory','Monthly TNS · actuals and approved forecasts');finance_chart('exec_tns')
    with right:
        with st.container(border=True):
            section('Marketplace mix','Store GMV contribution · selected interval')
            x=monthly(shop)
            if x.empty or x.gmv.isna().any():st.info('Comparable GMV is unavailable.')
            else:donut(x.groupby('marketplace',as_index=False).gmv.sum(),'marketplace','gmv','exec_mix')
    with st.expander('Detailed performance matrix',expanded=False):
        st.caption('Ratio differences are percentage points. Relative rate changes appear separately under YoY %. Annual attainment is shown for volume metrics only; rate targets are benchmarks.')
        table(pd.DataFrame(matrix),'executive')

elif page=='Financial performance':
    ytd=monthly(fin,date(year,1,1),end);actual=total(ytd,'tns');forecast=total(exact_forecast(date(year,1,1),end,'official'),'tns');target=total(annual_target(),'tns')
    remaining=None if actual is None or target is None else max(0,target-actual)
    df=financial_months()
    latest=df.iloc[month-1]
    metric_row([('YTD net sales',fmt(actual,'money')),('YTD forecast',fmt(forecast,'money')),('Forecast attainment',fmt(divide(actual,forecast,100),'pct')),('Variance to forecast',fmt(pp(actual,forecast),'money'))])
    st.write('')
    with st.container(border=True):section('Monthly TNS — Actual vs Forecast','Full year · missing actual months remain blank');finance_chart('financial_main')
    metric_row([('Full-year target',fmt(target,'money')),('Remaining to target',fmt(remaining,'money')),('Required / remaining month',fmt(divide(remaining,12-month),'money')),('Latest month YoY / MoM',fmt(latest['YoY %'],'pct')+' / '+fmt(latest['MoM %'],'pct'))])
    a,b=st.tabs(['Monthly performance','Cumulative YTD'])
    with a:table(df,'finance_monthly',['YoY %','MoM %','Variance'])
    with b:
        cumulative=df[['Month','Previous year','Current year','Official forecast','Stretch forecast']].copy()
        for col in cumulative.columns[1:]:
            # Once a month is missing, do not silently turn an incomplete series into YTD.
            cumulative[col]=pd.to_numeric(cumulative[col],errors='coerce').cumsum(skipna=False)
        plot(combo(cumulative.set_index('Month'),[],['Current year','Official forecast'],marketplace='Bosch'), 'finance_cumulative')
        table(cumulative,'finance_ytd')

elif page=='Marketplace performance':
    a,b=comparable_dates(start,end);cur=monthly(shop);old=monthly(shop,a,b)
    metric_row([('Store GMV',fmt(total(cur,'gmv'),'money'),number(growth(total(cur,"gmv"),total(old,"gmv")),st.session_state['decimal_places'],True)+'% YoY' if growth(total(cur,'gmv'),total(old,'gmv')) is not None else None),('Orders',fmt(total(cur,'orders'))),('Units sold',fmt(total(cur,'units'))),('AOV · GMV',fmt(divide(total(cur,'gmv'),total(cur,'orders')),'money'))])
    st.write('')
    tab1,tab2,tab3=st.tabs(['Monthly detail','YTD marketplace comparison','Daily performance'])
    allrows=[]
    for c,p in shop[['country','marketplace']].drop_duplicates().itertuples(index=False):
        rows=[]
        for period in months:
            s=shop[(shop.country==c)&(shop.marketplace==p)]
            x=s[s.period==period];prev=s[s.period==previous_month(period)];ly=s[s.period==previous_year_period(period)]
            ts=traffic[(traffic.country==c)&(traffic.marketplace==p)]
            e=f'{period}-{calendar.monthrange(year,int(period[-2:]))[1]}'
            uv,buyers=exact_audience(ts,f'{period}-01',e)
            lyperiod=previous_year_period(period);pe=previous_month(period)
            uvly,_=exact_audience(ts,lyperiod+'-01',f'{lyperiod}-{calendar.monthrange(year-1,int(period[-2:]))[1]}')
            puv,pbuyers=exact_audience(ts,pe+'-01',str(pd.Period(pe,'M').end_time.date()))
            revenue=total(x,'gmv');g=growth(revenue,total(ly,'gmv'));mom=growth(revenue,total(prev,'gmv'));cr=divide(buyers,uv,100)
            flag=uv is not None and puv is not None and uv>puv and ((mom is not None and mom<0) or (cr is not None and divide(pbuyers,puv,100) is not None and cr<divide(pbuyers,puv,100)))
            rows.append({'Month':calendar.month_abbr[int(period[-2:])],'Country':c,'Marketplace':p,'GMV':revenue,'PY GMV':total(ly,'gmv'),'YoY %':g,'MoM %':mom,'Visitors':uv,'PY visitors':uvly,'Visitor YoY %':growth(uv,uvly),'Visitor MoM %':growth(uv,puv),'Buyers':buyers,'CR %':cr,'Orders':total(x,'orders'),'Units':total(x,'units'),'AOV':divide(revenue,total(x,'orders')),'Traffic alert':'Traffic ↑ · GMV / CR ↓' if flag else ''})
        data=pd.DataFrame(rows);allrows.extend(rows)
        with tab1:
            with st.container(border=True):
                section(f'{p} · {"Malaysia" if c=="MY" else "Singapore"}')
                one,two=st.columns([1.6,1])
                with one:plot(combo(data.set_index('Month'),['GMV','PY GMV'],['YoY %'],report_currency,True,marketplace=p),f'market_{c}_{p}')
                with two:plot(combo(data.set_index('Month'),['Visitors','PY visitors'],['CR %'],second_axis=True,marketplace=p),f'traffic_{c}_{p}')
                alerts=data[data['Traffic alert']!='']
                if not alerts.empty:st.warning('Traffic opportunity: '+', '.join(alerts.Month)+'. Traffic rose while GMV or conversion fell compared with the preceding month.')
                table(data,f'market_detail_{c}_{p}',['YoY %','MoM %','Visitor YoY %','Visitor MoM %'])
    with tab2:
        if cur.empty:st.info('Import monthly shop performance to compare marketplaces.')
        else:
            rows=[]
            for (c,p),x in cur.groupby(['country','marketplace']):
                z=old[(old.country==c)&(old.marketplace==p)]
                u,v=exact_audience(traffic[(traffic.country==c)&(traffic.marketplace==p)],start,end)
                rows.append({'Store':f'{c} · {p}','GMV':total(x,'gmv'),'PY GMV':total(z,'gmv'),'YoY %':growth(total(x,'gmv'),total(z,'gmv')),'Contribution %':divide(total(x,'gmv'),total(cur,'gmv'),100),'Orders':total(x,'orders'),'Units':total(x,'units'),'Unique visitors':u,'Unique buyers':v,'CR %':divide(v,u,100)})
            y=pd.DataFrame(rows);y[['GMV','PY GMV']]=y[['GMV','PY GMV']].apply(pd.to_numeric,errors='coerce')
            comparison_fig=go.Figure()
            for field,previous in [('GMV',False),('PY GMV',True)]:
                colors=[marketplace_theme('Shopee' if 'Shopee' in label else 'Lazada')[1 if previous else 0] for label in y.Store]
                comparison_fig.add_bar(x=y.Store,y=y[field],name=field,marker_color=colors)
            comparison_fig.update_layout(barmode='group')
            plot(comparison_fig,'market_ytd');table(y,'market_ytd',['YoY %'])
            if allrows:
                heat=pd.DataFrame(allrows).pivot(index=['Country','Marketplace'],columns='Month',values='YoY %').reindex(columns=[calendar.month_abbr[i] for i in range(1,13)])
                heat.index=[' · '.join(i) for i in heat.index]
                plot(px.imshow(heat,color_continuous_scale=['#D95A68','#FFFFFF','#168A70'],color_continuous_midpoint=0,aspect='auto',labels={'color':'YoY %'}),'market_heatmap',240)

    with tab3:
        st.caption('Daily source records are separate from monthly summaries. Visitors and buyers are shown per store/day; they are never summed into monthly or YTD unique audiences.')
        daily=basis_filter(scoped(frames['marketplace_daily'])).copy()
        date_range=st.date_input('Daily date range',value=(max(start,date(year,month,1)),end),min_value=start,max_value=end,key=f'daily_dates_{year}_{month}_{period_mode}')
        if len(date_range)==2 and not daily.empty:
            daily['period']=daily.date.str[:7]
            daily=convert(daily,['gmv'],report_currency,frames['fx'],fx_method)
            daily=daily[(daily.date>=str(date_range[0]))&(daily.date<=str(date_range[1]))]
            for (c,p),x in daily.groupby(['country','marketplace']):
                section(f'{p} · {c} · daily')
                x=x.copy();x['Buyer CR %']=x.apply(lambda r:divide(r.buyers,r.visitors,100),axis=1)
                plot(combo(x.set_index('date'),['gmv'],['Buyer CR %'],report_currency,True,marketplace=p),'daily_'+c+p)
                table(x.drop(columns=['fx_missing','period'],errors='ignore'),'daily_'+c+p)
        else:st.info('No daily source records in this workspace. Monthly files cannot be expanded into invented daily records.')

elif page in ['Product & SKU','Conversion analysis']:
    listing_mode=False
    identity=st.selectbox('Product reporting grain',['Marketplace product listings','Sellable variant detail','Approved Bosch SKUs'],index=2 if mode=='Demo workspace' else 0)
    if identity=='Sellable variant detail':
        st.caption('Sellable variant rows are shown separately from product totals. Seller SKU is source-reported; product visitors are never allocated to variants. Canonical cross-market matching and BU classification require approval.')
        variants=basis_filter(scoped(frames['listing_variants'])).copy()
        variants=variants[variants.period==current]
        variants=convert(variants,['revenue'],report_currency,frames['fx'],fx_method)
        if not variants.empty:
            variants['ASP']=variants.apply(lambda r:divide(r.revenue,r.units),axis=1)
            variants=variants.sort_values('revenue',ascending=False)
            table(variants.drop(columns=['fx_missing'],errors='ignore'),'variant_detail')
        else:st.info('No variant records for this store, month and order basis.')
        st.stop()
    if identity=='Marketplace product listings':
        listing_mode=True
        products=money_frame('listing_products',['revenue'])
        master=products.sort_values('period').drop_duplicates(['country','marketplace','listing_sku'],keep='last')[['country','marketplace','listing_sku','product_name','source_material']].copy()
        master['canonical_sku']=master.country+':'+master.marketplace+':'+master.listing_sku
        master['business_unit']='Unmapped';master['product_group']='Unmapped';master['is_bundle']=None;master['mapping_status']='Source listing · Bosch mapping pending'
        missing_scopes=[f'{c} · {p}' for c,p in scope_grid if products[(products.country==c)&(products.marketplace==p)&(products.period==current)].empty]
        if missing_scopes:st.warning('No product records for: '+', '.join(missing_scopes)+'. Product totals cover available sources only; Paid Order SKU data is not included in the supplied Shopee files.')
        st.info('Listing-level reporting uses source product totals, with variants excluded. Bosch material text is source-reported; canonical mapping, BU, product group, bundle classification and finance GM remain unapproved.')
        quality=product_store_reconciliation(frames['listing_products'],frames['marketplace'])
        if not quality.empty:
            flags=quality[(quality.Status=='Mismatch')&quality.Period.isin([current,previous])]
            if country:flags=flags[flags.Country==country]
            if marketplace!='All marketplaces':flags=flags[flags.Marketplace==marketplace]
            flags=flags[(flags.Marketplace!='Shopee')|(flags['Sales basis']==order_basis)]
            if not flags.empty:
                st.warning('Product totals do not reconcile with shop totals for a comparison period. Review file periods before relying on movement or share metrics.')
                table(flags,'product_reconciliation_flags')
        if not products.empty and (products.marketplace=='Shopee').any():st.caption('Shopee product periods come from the supplied filename / explicit month, because no report interval is embedded in these workbooks.')
    else:master=scoped(frames['sku_master'])
    if bu:master=master[master.business_unit.isin(bu)]
    if groups:master=master[master.product_group.isin(groups)]
    if skus:master=master[master.canonical_sku.isin(skus)]
    products=products.merge(master[['country','marketplace','listing_sku']],on=['country','marketplace','listing_sku'],how='inner')
    st.caption(f'Product reporting uses the final selected month ({current}) against {previous}. Ranks and shares use the complete filtered assortment before Top N is applied.')
    n_label=st.selectbox('Ranking depth',['Top 10','Top 20','Top 50','All products'],index=1)
    limit={'Top 10':10,'Top 20':20,'Top 50':50,'All products':999999}[n_label]
    ranked=ranked_products(products,master,current,previous)
    if ranked.empty:
        st.info('No approved full SKU performance is available for this month. Import a complete product-performance export and approved SKU master to enable rankings and conversion analysis.')
        excerpts=basis_filter(scoped(frames['contributions']))
        excerpts=excerpts[excerpts.period==current]
        if not excerpts.empty:
            section('Source product contribution excerpts','Shopee channel excerpts only. Product clicks are not SKU visitors. Channels and order bases must not be added into product or store totals.')
            channel=st.selectbox('Source channel',sorted(excerpts.channel.unique()))
            excerpts=convert(excerpts[excerpts.channel==channel],['revenue'],report_currency,frames['fx'],fx_method)
            table(excerpts.drop(columns='fx_missing'),'source_contributions')
        st.stop()
    if page=='Product & SKU':
        top=ranked.head(limit)
        metric_row([('Assortment revenue',fmt(total(ranked,'revenue'),'money')),('Listings selling' if listing_mode else 'Products selling',fmt(int((ranked.units>0).sum()))),('Units sold',fmt(total(ranked,'units'))),('Top selection share',fmt(divide(total(top,'revenue'),total(ranked,'revenue'),100),'pct'))])
        st.write('')
        a,b,c=st.tabs(['SKU rankings','Business unit analysis','Rank movement'])
        with a:
            columns=['rank','previous_rank','rank_movement','canonical_sku','product_name','business_unit','product_group','revenue','units','asp','gm_pct','share','marketplace','period','is_bundle','source_material','mapping_status','status']
            table(top[columns],'product_rankings',['rank_movement'])
        with b:
            if listing_mode:st.info('BU and product-group classifications require an approved Bosch SKU master. Unmapped amounts below show classification coverage only.')
            rows=[]
            for unit,x in ranked.groupby('business_unit'):
                old=products[(products.period==previous)].merge(master[['country','marketplace','listing_sku','business_unit']],on=['country','marketplace','listing_sku'])
                old=old[old.business_unit==unit]
                r=total(x,'revenue')
                rows.append({'Business unit':unit,'Revenue':r,'Contribution %':divide(r,total(ranked,'revenue'),100),'Units':total(x,'units'),'ASP':divide(r,total(x,'units')),'GM %':weighted_rate(products[(products.period==current)].merge(master[master.business_unit==unit][['country','marketplace','listing_sku']],on=['country','marketplace','listing_sku']),'gm_pct','gm_basis'),'Previous month revenue':total(old,'revenue'),'MoM %':growth(r,total(old,'revenue'))})
            data=pd.DataFrame(rows);left,right=st.columns([1,1.5])
            with left:donut(data,'Business unit','Revenue','bu_donut')
            with right:
                split=products[products.period.isin([current,previous])].merge(master[['country','marketplace','listing_sku','business_unit']],on=['country','marketplace','listing_sku'])
                plot(px.bar(split.groupby(['period','business_unit'],as_index=False).revenue.sum(min_count=1),x='period',y='revenue',color='business_unit',barmode='stack',color_discrete_sequence=marketplace_theme(marketplace)+['#9CAFC0']),'bu_stacked')
            table(data,'bu_analysis',['MoM %'])
        with c:
            table(top[['rank','previous_rank','rank_movement','product_name','status','revenue_change','units_change','share_pp']],'rank_movement',['rank_movement','revenue_change','units_change','share_pp'])
            oldrank=ranked_products(products,master,previous,previous_month(previous))
            if not oldrank.empty:
                dropped=oldrank[oldrank['rank']<=limit][~oldrank.canonical_sku.isin(top.canonical_sku)]
                st.caption('Dropped out of the selected Top N (only meaningful when both months have complete assortment coverage).')
                table(dropped[['canonical_sku','product_name','rank']],'dropped_products')
            st.caption('New entrant means absent from the preceding imported month, not necessarily a newly launched product. Missing source history is identified separately.')
    else:
        cfg=st.columns(5)
        with cfg[0]:min_traffic=st.number_input('Filter · min visitors',0,value=0,step=50)
        with cfg[1]:min_units=st.number_input('Minimum units',0,value=0)
        with cfg[2]:min_buyers=st.number_input('Evidence · min buyers',0,value=5)
        with cfg[3]:max_price=st.number_input(f'Max ASP · {report_currency}',min_value=0.0,value=10000.0)
        with cfg[4]:min_price=st.number_input(f'Min ASP · {report_currency}',min_value=0.0,value=0.0)
        price_match=((ranked.asp<=max_price)&(ranked.asp>=min_price)) | (ranked.asp.isna() & (min_price==0))
        x=ranked[(ranked.units>=min_units)&price_match].copy()
        if min_traffic>0:x=x[x.visitors>=min_traffic]
        bench=st.columns(4)
        with bench[0]:min_evidence=st.number_input('Evidence · min visitors',0,value=100,step=50)
        eligible=x[(x.visitors>=min_evidence)&(x.buyers>=min_buyers)]
        with bench[1]:benchmark_mode=st.selectbox('Benchmark',['Product-group median','Manual'],index=1 if listing_mode else 0)
        with bench[2]:traffic_benchmark=st.number_input('Traffic threshold',min_value=1.0,value=float(eligible.visitors.median()) if not eligible.empty else 1000.0,disabled=benchmark_mode!='Manual')
        with bench[3]:cr_benchmark=st.number_input('Conversion threshold %',min_value=0.0,max_value=100.0,value=float(eligible.cr.median()) if not eligible.empty else 2.0,disabled=benchmark_mode!='Manual')
        def classify(r):
            peers=eligible[eligible.product_group==r.product_group]
            if benchmark_mode=='Product-group median' and r.product_group=='Unmapped':return 'Category mapping required'
            if benchmark_mode=='Product-group median' and len(peers)<3:return 'Insufficient peer group'
            return opportunity(r,float(peers.visitors.median()) if benchmark_mode!='Manual' else traffic_benchmark,float(peers.cr.median()) if benchmark_mode!='Manual' else cr_benchmark,min_evidence,min_buyers)
        x['Opportunity']=x.apply(classify,axis=1)
        st.caption('Default listing analysis uses explicit manual benchmarks until categories are approved. Group benchmarks require at least 3 eligible comparable products. Products below evidence thresholds are unclassified. Consolidated SKU audience remains unavailable across listings.')
        if not x.empty:
            scatter=x.dropna(subset=['visitors','cr','revenue'])
            if not scatter.empty:
                plot(px.scatter(scatter,x='visitors',y='cr',size='revenue',color='Opportunity',hover_name='product_name',labels={'visitors':'Product visitors','cr':'Buyer conversion %'},color_discrete_sequence=marketplace_theme(marketplace)+[NAVY]),'opportunity',380)
        tabs=st.tabs(['Consolidated selection','Shopee vs Lazada'])
        conversion_cols=['rank','product_name','canonical_sku','business_unit','revenue','units','visitors','buyers','cr','atc_units','asp','share','Opportunity','revenue_change','units_change','visitors_change','buyers_change','cr_pp','atc_units_change','asp_change','share_pp']
        with tabs[0]:table(x.head(limit)[conversion_cols],'conversion',['revenue_change','units_change','visitors_change','buyers_change','cr_pp','atc_units_change','asp_change','share_pp'])
        with tabs[1]:
            left,right=st.columns(2)
            for col,platform in zip([left,right],['Shopee','Lazada']):
                with col:
                    section(platform)
                    m=master[master.marketplace==platform].copy()
                    p=products[products.marketplace==platform].copy()
                    # Keep the same approved product filters in both panels.
                    if bu:m=m[m.business_unit.isin(bu)]
                    if groups:m=m[m.product_group.isin(groups)]
                    if skus:m=m[m.canonical_sku.isin(skus)]
                    p=p.merge(m[['country','marketplace','listing_sku']],on=['country','marketplace','listing_sku'])
                    r=ranked_products(p,m,current,previous)
                    if not r.empty:
                        r=r[(r.units>=min_units)&(r.asp>=min_price)&(r.asp<=max_price)]
                        if min_traffic>0:r=r[r.visitors>=min_traffic]
                    if r.empty:st.info('No comparable products in this store scope.')
                    else:table(r.head(limit)[[c for c in conversion_cols if c in r]],'side_'+platform,['revenue_change','cr_pp'])
        st.caption('Evidence thresholds govern classification; visitor and units filters govern displayed products. Select All marketplaces to populate both comparison panels.')

elif page=='Advertising performance':
    selected=monthly(ads)
    models=sorted(selected.attribution_model.dropna().unique())
    model=st.selectbox('Attribution scope',['Compare separately']+models)
    if model!='Compare separately':selected=selected[selected.attribution_model==model]
    compatible=len(selected.attribution_model.dropna().unique())<=1
    spend=total(selected,'spend') if compatible else None;ads_gmv=total(selected,'ads_gmv') if compatible else None
    metric_row([('Advertising spend',fmt(spend,'money')),('Attributed GMV',fmt(ads_gmv,'money')),('ROAS · compatible scope',fmt(divide(ads_gmv,spend) if compatible else None,'decimal')),('ACOS · compatible scope',fmt(divide(spend,ads_gmv,100) if compatible else None,'pct'))])
    if not compatible:st.info('Attribution models differ. Combined totals and efficiency ratios are unavailable because attribution scopes may overlap; review each scope separately below.')
    st.write('')
    comparison=[]
    scopes=selected[['country','marketplace','attribution_model']].drop_duplicates()
    for c,p,attr in scopes.itertuples(index=False):
        if pd.isna(attr):continue
        rows=[]
        base=ads[(ads.country==c)&(ads.marketplace==p)&(ads.attribution_model==attr)]
        for period in months:
            x=base[base.period==period];prev=base[base.period==previous_month(period)]
            s=total(x,'spend');g=total(x,'ads_gmv');roas=divide(g,s)
            shop_gmv=None if 'unverified' in attr else total(shop[(shop.country==c)&(shop.marketplace==p)&(shop.period==period)],'gmv')
            rows.append({'Month':calendar.month_abbr[int(period[-2:])],'Country':c,'Marketplace':p,'Attribution model':attr,'Ad spend':s,'Ads GMV':g,'ROAS':roas,'ACOS %':divide(s,g,100),'Cost / ad order':divide(s,total(x,'ad_orders')),'Spend / store GMV %':divide(s,shop_gmv,100),'MoM spend %':growth(s,total(prev,'spend')),'MoM ROAS %':growth(roas,divide(total(prev,'ads_gmv'),total(prev,'spend')))})
        d=pd.DataFrame(rows);comparison.extend(rows)
        with st.container(border=True):
            section(f'{p} paid ads performance · {c}',f'{attr} · full-year monthly detail')
            if 'unverified' in attr:st.warning('BRM source-reported spend and Ads GMV. Attribution/order status is unverified. Ratios to Confirmed Order store GMV are unavailable; within-report ROAS/ACOS are recalculated from the entered amounts.')
            f=go.Figure()
            palette=marketplace_theme(p)
            for label,color in [('Ad spend',palette[0]),('Ads GMV',palette[1])]:f.add_bar(x=d.Month,y=d[label],name=label,marker_color=color)
            f.add_scatter(x=d.Month,y=d.ROAS,name='Actual ROAS',yaxis='y2',line=dict(color=palette[2],width=3),mode='lines+markers')
            f.update_layout(barmode='group',yaxis2=dict(overlaying='y',side='right',showgrid=False,ticksuffix='×'))
            plot(f,'ads_'+c+p+attr)
            scope_selected=base[(base.period>=str(start)[:7])&(base.period<=str(end)[:7])]
            sg=None if 'unverified' in attr else total(monthly(shop[(shop.country==c)&(shop.marketplace==p)]),'gmv')
            metric_row([('Period ROAS',fmt(divide(total(scope_selected,'ads_gmv'),total(scope_selected,'spend')),'decimal')),('Period ACOS',fmt(divide(total(scope_selected,'spend'),total(scope_selected,'ads_gmv'),100),'pct')),('Cost per ad order',fmt(divide(total(scope_selected,'spend'),total(scope_selected,'ad_orders')),'money')),('Spend / store GMV',fmt(divide(total(scope_selected,'spend'),sg,100),'pct'))])
    if comparison:table(pd.DataFrame(comparison),'advertising',['MoM ROAS %'])
    else:st.info('Import monthly advertising data with an explicit attribution model to display performance.')

elif page=='Data workspace':
    st.info('Imports go to the uploaded-data workspace. The synthetic demonstration remains separate. Switch Data source to Uploaded data to review imported results.')
    prepared_path=Path(__file__).parent/'prepared'/'my-workspace.enc'
    if prepared_path.is_file():
        section('Load prepared actual data','Your previously supplied exports are available as an encrypted package. Paste the separate transfer key to load them; no download or file upload is needed.')
        with st.form('prepared_data',clear_on_submit=True):
            transfer_key=st.text_input('Transfer key',type='password')
            replace_prepared=st.checkbox('Replace conflicting records with the prepared data')
            load_prepared=st.form_submit_button('Load prepared actual data',type='primary')
        if load_prepared:
            try:
                with st.spinner('Validating and importing your prepared data…'):
                    unlocked=decrypt_workspace(prepared_path.read_bytes(),transfer_key)
                    result=import_workspace(store,unlocked,'prepared-actual-data.zip',replace_prepared)
                if result['status']=='rejected':st.error(result['detail'])
                else:st.success('Actual data loaded. Select Uploaded data in the sidebar to view your reports.')
            except ValueError as exc:st.error(str(exc))
    if not os.environ.get('BOSCH_BI_DB'):
        st.warning('Development storage is local SQLite. Production requires BOSCH_BI_DB on a persistent mounted volume, authenticated hosting, backups and restricted file access. This runtime is not configured as durable production storage.')
    with st.expander('Transfer existing workspace · one file',expanded=True):
        st.caption('Load a prepared Bosch workspace package to transfer all datasets together. Original import history is retained in the audit trail. This private data file must stay out of GitHub.')
        package=st.file_uploader('Upload workspace package',type=['zip'],key='workspace_package')
        if package is not None:
            try:
                package_frames,_=read_workspace(package.getvalue())
                st.dataframe(pd.DataFrame([{'Dataset':SCHEMAS[k].title,'Rows':len(v)} for k,v in package_frames.items()]),hide_index=True,width='stretch')
                replace_package=st.checkbox('Replace conflicting records with this package',key='replace_package')
                if st.button('Import workspace package',type='primary'):
                    result=import_workspace(store,package.getvalue(),package.name,replace_package)
                    if result['status']=='rejected':st.error(result['detail'])
                    else:st.success('Workspace loaded. Select Uploaded data in the sidebar to view your reports.');st.info(result['detail'])
            except ValueError as exc:st.error(str(exc))
        if has_uploaded_data:
            if st.button('Prepare workspace backup'):
                st.download_button('Download private workspace backup',export_workspace(store),'bosch-workspace.zip','application/zip')
        st.caption('Keep a backup locally. Streamlit Community Cloud storage may reset; this transfer feature does not provide automatic persistent storage.')
    a,b,c=st.tabs(['Import & validate','Data coverage & history','Import contracts'])
    with a:
        section('Reporting data imports','Stage one or more CSV/XLSX or supported Lazada XLS files, confirm their columns and scope, then commit validated rows. Excel cells must contain values, not unevaluated formulas.')
        files=st.file_uploader('Upload canonical reports or stage raw exports for mapping',type=['csv','xlsx','xls'],accept_multiple_files=True)
        configs=store.configs()
        for i,file in enumerate(files or []):
            with st.expander(file.name,expanded=True):
                prefix=f'{i}_{file.name}'
                raw=file.getvalue()
                if len(raw)>20*1024*1024:st.error('The file exceeds the 20 MB limit.');continue
                try:
                    source_kind=adapter_kind(raw) if file.name.lower().endswith(('.xlsx','.xls')) else None
                    if source_kind:
                        source_period=None
                        if source_kind=='shopee_products':
                            source_period=st.text_input('Verify reporting month · YYYY-MM (not embedded in workbook)',value=period_from_filename(file.name) or '',key='src_period_'+prefix)
                        source=parse_source(raw,source_kind,period=source_period)
                        st.success('Recognized inspected source: '+source.kind)
                        for note in source.notes:st.caption(note)
                        for key,frame in source.datasets.items():
                            st.write(f'{SCHEMAS[key].title}: {len(frame):,} rows')
                            st.dataframe(frame.head(5),hide_index=True,width='stretch')
                        if source.checks:
                            st.dataframe(pd.DataFrame(source.checks),hide_index=True,width='stretch')
                            if any(check['status']!='Matches' for check in source.checks):st.warning('Source totals differ from daily / component totals. Monthly source summaries remain authoritative; review these differences.')
                        replace_source=st.checkbox('Replace conflicting source records after review',key='src_replace_'+prefix)
                        reviewed_source=st.checkbox('Use the inspected Malaysia source scope and preserve all separate order bases',key='src_review_'+prefix)
                        if st.button('Import inspected source workbook',type='primary',disabled=not reviewed_source,key='src_commit_'+prefix):
                            result=store.ingest_bundle(source.datasets,file.name,replace_source,notes={'notes':source.notes,'checks':source.checks})
                            (st.error if result['status']=='rejected' else st.success)(result['detail'])
                        continue
                    if file.name.lower().endswith('.xls'):
                        st.error('This XLS schema is not recognized. Inspect it before building an adapter; generic mapping currently supports CSV/XLSX.');continue
                    if file.name.lower().endswith('.xlsx'):
                        import zipfile
                        with zipfile.ZipFile(BytesIO(raw)) as archive:
                            if sum(item.file_size for item in archive.infolist())>100*1024*1024:raise ValueError('Expanded workbook exceeds the 100 MB safety limit.')
                        workbook=pd.ExcelFile(BytesIO(raw),engine='openpyxl')
                        sheet=st.selectbox('Worksheet',workbook.sheet_names,key='sheet_'+prefix)
                        raw_df=pd.read_excel(workbook,sheet_name=sheet,dtype=object)
                    else:raw_df=pd.read_csv(BytesIO(raw),dtype=object)
                    if len(raw_df)>100000:st.error('Maximum 100,000 rows per staged file. Split larger reports.');continue
                except Exception as exc:st.error(f'Unable to parse report: {exc}');continue
                st.caption(f'{len(raw_df):,} rows · {len(raw_df.columns)} columns · original file stays in memory')
                st.dataframe(raw_df.head(8),hide_index=True,width='stretch')
                profile=st.selectbox('Saved mapping',['New mapping']+list(configs),key='profile_'+prefix)
                saved=configs.get(profile,{})
                suggested=saved.get('category',recognize(raw_df.columns))
                category=st.selectbox('Import category',list(SCHEMAS),index=list(SCHEMAS).index(suggested),format_func=lambda k:SCHEMAS[k].title,key='category_'+prefix)
                spec=SCHEMAS[category];st.caption(spec.note)
                mapping=saved.get('mapping',suggest_mapping(raw_df.columns,category))
                choices=['— Unmapped —']+list(raw_df.columns)
                selected_map={}
                with st.expander('Column mapping · required fields marked *',expanded=True):
                    cols=st.columns(3)
                    for j,field in enumerate(spec.required+spec.optional):
                        with cols[j%3]:
                            value=mapping.get(field)
                            chosen=st.selectbox(field+(' *' if field in spec.required else ''),choices,index=choices.index(value) if value in choices else 0,key=f'map_{prefix}_{category}_{field}_{profile}')
                            if chosen!=choices[0]:selected_map[field]=chosen
                context={}
                with st.expander('Explicit scope / period defaults for missing fields'):
                    st.caption('Defaults fill unmapped columns only. Verify these values against the source report; they are never inferred from the filename.')
                    for field in ['country','marketplace','period','currency','period_start','period_end','attribution_model','scenario']:
                        if field in spec.required and field not in selected_map:
                            v=st.text_input(field,key=f'context_{prefix}_{category}_{field}',value=saved.get('context',{}).get(field,''))
                            if v:context[field]=v
                normalized=pd.DataFrame({canonical:raw_df[source] for canonical,source in selected_map.items()})
                if normalized.empty and len(raw_df):normalized=pd.DataFrame(index=raw_df.index)
                for k,v in context.items():normalized[k]=v
                if len(selected_map.values())!=len(set(selected_map.values())):st.error('A source column is mapped more than once. Review the mapping.');continue
                clean,errors=validate(category,normalized,store.read('sku_master'))
                if errors:
                    for error in errors:st.error(error)
                else:st.success(f'{len(clean):,} rows pass schema checks. Existing-record conflicts are checked transactionally on commit.')
                cfg_name=st.text_input('Save mapping as',value=f'{category} mapping',key='cfgname_'+prefix)
                if st.button('Save import configuration',key='save_cfg_'+prefix):
                    store.save_config(cfg_name,dict(category=category,mapping=selected_map,context=context));st.success('Mapping saved to the reporting database.')
                replace=st.checkbox('Replace conflicting business keys after review',value=False,key='replace_'+prefix)
                reviewed=st.checkbox('I verified report grain, period, source units, audience scope and finance definitions',key='reviewed_'+prefix)
                if st.button('Commit validated import',type='primary',disabled=bool(errors) or not reviewed,key='commit_'+prefix):
                    result=store.ingest(category,clean,file.name,replace)
                    if result['status']=='imported':st.success(result['detail'])
                    elif result['status']=='duplicate':st.info(result['detail'])
                    else:st.error(result['detail'])
    with b:
        coverage=[]
        for k,s in SCHEMAS.items():
            x=store.read(k)
            periods=x['period'].dropna() if 'period' in x else x.get('period_start',x.get('date',pd.Series(dtype=str))).dropna()
            coverage.append({'Dataset':s.title,'Records':len(x),'First period':periods.min() if len(periods) else None,'Last period':periods.max() if len(periods) else None})
        table(pd.DataFrame(coverage),'coverage')
        section('Import audit trail','Accepted, rejected and replacement imports. Each stored row retains its import ID.')
        table(store.history(),'import_history')
        st.caption('Duplicate file submissions are idempotent and do not alter data. Identical normalized reports are identified even when filenames change.')
        section('Product exports vs shop totals','Compares item-total rows only, by marketplace, month, order basis and source currency. Tolerance: 0.05. Variant rows are excluded.')
        product_checks=product_store_reconciliation(store.read('listing_products'),store.read('marketplace'))
        table(product_checks,'product_source_reconciliation',['Difference'])
        section('Reference calculation checks')
        st.write('Example: 120 / 100 − 1 = **20% YoY**. 120 / 150 = **80% forecast attainment**. Actual reporting is recalculated from uploaded source data.')
        checks=[]
        financial=store.read('financial_actuals')
        for _,r in financial.iterrows():
            calculated=divide(r.get('tns'),r.get('orders'))
            if pd.notna(r.get('reported_aov')):
                checks.append({'Dataset':'Finance','Period':r.period,'Store':f'{r.country} · {r.marketplace}','Metric':'TNS AOV','Source':r.reported_aov,'Calculated':calculated,'Status':reconciliation(calculated,r.reported_aov)})
        for _,r in store.read('traffic').iterrows():
            calculated=divide(r.get('buyers'),r.get('visitors'),100)
            if pd.notna(r.get('reported_cr_pct')):
                checks.append({'Dataset':'Traffic','Period':r.period_start+' / '+r.period_end,'Store':f'{r.country} · {r.marketplace}','Metric':'CR %','Source':r.reported_cr_pct,'Calculated':calculated,'Status':reconciliation(calculated,r.reported_cr_pct)})
        if checks:table(pd.DataFrame(checks),'reconciliation')
        else:st.caption('Import optional reported_aov (finance) and reported_cr_pct (traffic) to compare source-reported values with independent calculations. Tolerance: 0.05 source units / percentage points. More source-specific checks require actual export schemas.')
    with c:
        for k,s in SCHEMAS.items():
            with st.expander(s.title):
                st.write(s.note);st.write('Business key: '+', '.join(s.keys));st.write('Required: '+', '.join(s.required));st.write('Optional: '+', '.join(s.optional))
                st.download_button('Download blank CSV template',template(k),f'{k}_template.csv','text/csv',key='tpl_'+k)
        st.caption('Canonical contracts are configurable. Inspected Shopee MY XLSX, Lazada MY XLS and internal MY TNS workbook adapters are available above; new schemas still require review. Source contribution excerpts are stored separately from approved SKU performance.')

elif page=='Reporting methodology':
    section('Trustworthy reporting, with explicit limits')
    st.markdown('''
- **TNS and finance rates:** imported from finance-approved sources. GM, returns and cost concession have no invented company formula. Multiple rates require complete approved weighting bases. `gm_basis` and `concession_basis` are monetary denominators in the row currency; `return_basis` is a comparable count denominator.
- **Conversion rate:** unique buyers ÷ unique visitors × 100, for one store and one exact interval. Monthly unique audiences cannot be added into YTD unique audiences. Cross-store unique totals are unavailable without a deduplicated source.
- **AOV:** TNS ÷ finance orders on finance pages; GMV ÷ shop orders on marketplace pages. Product ASP is revenue ÷ units.
- **Comparisons:** YoY = (actual ÷ comparable prior-year actual − 1) × 100. MoM uses the immediately preceding calendar month, including January → December. Leap-day prior-year comparisons clamp to February 28.
- **Ratios:** show percentage-point differences separately from relative growth. Lower return and concession rates are favorable. Weighted rates require approved denominators for every underlying row.
- **Forecasts:** official and stretch values come only from imports. Annual targets are separate from monthly forecasts. Annual targets use the chosen currency or the fixed EUR/MYR rate; annual SGD conversions require an approved method. Zero denominators and unavailable comparisons show a dash.
- **FX:** explicit monthly source-to-target multiplier using the selected methodology. EUR/MYR always follows the user-approved fixed rate 4.64 (MYR/EUR = 1/4.64); other pairs require imported rates. No cross-rate or carry-forward is inferred. Missing FX produces missing monetary values, never a plausible partial sum.
- **Advertising:** ROAS = attributed ads GMV ÷ spend; ACOS = spend ÷ attributed ads GMV × 100. Attribution-model scopes are kept separate for efficiency ratios.
- **Products:** approved canonical sellable-SKU mapping, stable tie-breaking by canonical SKU, and independent bundle identity. Product audiences across listings are unavailable without deduplication. Rank movement is prior rank minus current rank.
- **Opportunities:** configurable traffic and CR thresholds; default product-group medians use at least three eligible products. Minimum visitors and buyers prevent classifications based on tiny samples.
- **Missing data:** a dash means unavailable, not zero. Future actual months remain blank. Financial adjustments and source-defined negative net measures require a reviewed extension to the conservative nonnegative import contract.
''')
    section('Operational readiness')
    st.write('Phase 1 is a local Streamlit reporting foundation. Use authenticated hosting with a persistent volume for SQLite, scheduled backups and a single application writer. Shared multi-instance production hosting should use managed PostgreSQL with migrations and access controls. Those deployment integrations are a next-phase task.')
    st.write('Daily marketplace reporting is supported for the inspected Shopee/Lazada files; daily finance, SKU and ads reporting need their own source schemas. Product reporting is monthly; advanced product filters apply only to product modules. Finance and store-level sources cannot safely be sliced by SKU or BU without allocated finance and shop data.')
    with st.expander('Required source review before production'):
        st.write('The inspected MY shop, product and TNS files are supported. Provide approved advertising attribution definitions, cost-concession definitions and finance weighting bases, scope-compatible audience reports, SKU/bundle mapping, FX methodology and forecast/target files. Review totals, unique-count scope and attribution windows with data owners before relying on management reports.')

st.divider()
st.caption('BOSCH POWER TOOLS  /  COMMERCE INTELLIGENCE     ·     '+('DEMO WORKSPACE · NOT FOR MANAGEMENT REPORTING' if mode=='Demo workspace' else 'UPLOADED DATA · REVIEW COVERAGE BEFORE REPORTING'))
