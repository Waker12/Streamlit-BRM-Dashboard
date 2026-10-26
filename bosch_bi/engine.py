"""Calculations return None for unavailable or mathematically undefined results."""
import calendar
from datetime import date
import pandas as pd
from .policy import fixed_rate


def divide(n, d, scale=1):
    if n is None or d is None or pd.isna(n) or pd.isna(d) or d == 0: return None
    return float(n) / float(d) * scale

def growth(actual, previous):
    value = divide(actual, previous)
    return None if value is None else (value-1)*100

def pp(actual, previous):
    if actual is None or previous is None or pd.isna(actual) or pd.isna(previous): return None
    return float(actual)-float(previous)

def favorable(delta, lower_is_better=False):
    return None if delta is None else (delta <= 0 if lower_is_better else delta >= 0)

def previous_month(period):
    return str(pd.Period(period, freq='M')-1)

def previous_year_period(period):
    return str(pd.Period(period, freq='M')-12)

def comparable_dates(start, end):
    def shift(d):
        d = pd.Timestamp(d).date()
        return date(d.year-1,d.month,min(d.day,calendar.monthrange(d.year-1,d.month)[1]))
    return shift(start), shift(end)

def total(df, field):
    if df.empty or field not in df or df[field].isna().any(): return None
    return float(df[field].sum())

def weighted_rate(df, rate, basis):
    if df.empty or rate not in df or df[rate].isna().any(): return None
    if len(df)==1: return float(df[rate].iloc[0])
    if basis not in df or df[basis].isna().any() or (df[basis]<0).any(): return None
    return divide((df[rate]*df[basis]).sum(),df[basis].sum())

def exact_audience(df, start, end):
    if df.empty: return None, None
    x=df[(df.period_start==str(start)) & (df.period_end==str(end))]
    # No cross-platform/country deduplication, even when intervals match.
    if len(x)!=1 or df[['country','marketplace']].drop_duplicates().shape[0]!=1: return None,None
    return tuple(float(x.iloc[0][field]) if field in x and pd.notna(x.iloc[0][field]) else None for field in ['visitors','buyers'])

def convert(df, fields, currency, fx, methodology):
    """Strict monthly FX join. Missing any required rate invalidates aggregate."""
    out=df.copy()
    out['fx_missing']=False
    for idx,row in out.iterrows():
        source=row.get('currency')
        rate=fixed_rate(source,currency)
        if rate is None:
            match=fx[(fx.period==row['period']) & (fx.from_currency==source) & (fx.to_currency==currency) & (fx.methodology==methodology)] if not fx.empty else pd.DataFrame()
            rate=float(match.iloc[0].rate) if len(match)==1 else None
        if rate is None:
            out.at[idx,'fx_missing']=True
        for field in fields:
            if field in out and pd.notna(row.get(field)):
                out.at[idx,field]=float(row[field])*rate if rate is not None else float('nan')
    return out

def ranked_products(df, master, current, previous):
    if df.empty: return pd.DataFrame()
    joined=df.merge(master,on=['country','marketplace','listing_sku'],how='left',suffixes=('','_master'),validate='many_to_one')
    keys=['canonical_sku']
    def period_rows(p):
        x=joined[joined.period==p]
        if x.empty: return pd.DataFrame()
        result=[]
        for sku,g in x.groupby(keys[0],dropna=False):
            row={k:g.iloc[0].get(k) for k in ['product_name','business_unit','product_group','is_bundle','source_material','mapping_status']}
            row['canonical_sku']=sku
            for field in ['revenue','units','atc_units']: row[field]=total(g,field)
            # SKU audience across listings/platforms is also not deduplicated.
            for field in ['visitors','buyers']: row[field]=float(g.iloc[0][field]) if len(g)==1 and field in g and pd.notna(g.iloc[0][field]) else None
            row['gm_pct']=weighted_rate(g,'gm_pct','gm_basis')
            row['marketplace']=', '.join(sorted(g.marketplace.unique()))
            row['period']=p
            result.append(row)
        r=pd.DataFrame(result).sort_values(['revenue','canonical_sku'],ascending=[False,True],na_position='last')
        r['rank']=range(1,len(r)+1)
        r['share']=r.revenue.apply(lambda v: divide(v,total(r,'revenue'),100))
        r['asp']=r.apply(lambda a:divide(a.revenue,a.units),axis=1)
        r['cr']=r.apply(lambda a:divide(a.buyers,a.visitors,100),axis=1)
        return r
    cur,prev=period_rows(current),period_rows(previous)
    if cur.empty:return cur
    fields=['rank','revenue','units','share','visitors','buyers','atc_units','asp','cr']
    if prev.empty:
        for f in fields: cur['previous_'+f]=float('nan')
        cur['status']='No history'
    else:
        p=prev[['canonical_sku']+fields].rename(columns={f:'previous_'+f for f in fields})
        cur=cur.merge(p,on='canonical_sku',how='left')
        cur['status']=cur.previous_rank.apply(lambda x:'New entrant' if pd.isna(x) else 'Continuing')
    cur['rank_movement']=cur.previous_rank-cur['rank']
    for f in ['revenue','units','visitors','buyers','atc_units','asp']:
        cur[f+'_change']=cur.apply(lambda a:growth(a[f],a['previous_'+f]),axis=1)
    for f in ['share','cr']:cur[f+'_pp']=cur.apply(lambda a:pp(a[f],a['previous_'+f]),axis=1)
    return cur

def opportunity(row, traffic_benchmark, cr_benchmark, min_visitors=100,min_buyers=5):
    if pd.isna(row.get('visitors')) or pd.isna(row.get('buyers')) or row['visitors']<min_visitors or row['buyers']<min_buyers:
        return 'Insufficient sample'
    high_t=row['visitors']>=traffic_benchmark
    high_c=row['cr']>=cr_benchmark
    return {(True,True):'Hero SKU',(True,False):'Optimize listing',(False,True):'Grow traffic',(False,False):'Investigate'}[(high_t,high_c)]

def complete_scopes(df, scopes):
    """Add explicit unavailable records for absent selected stores."""
    out=df.copy()
    missing=[]
    for country,marketplace in scopes:
        if out.empty or not ((out.country==country)&(out.marketplace==marketplace)).any():
            row={col:float('nan') for col in out.columns}
            row.update(country=country,marketplace=marketplace)
            missing.append(row)
    return pd.concat([out,pd.DataFrame(missing)],ignore_index=True) if missing else out

def complete_months(df,scopes,periods):
    out=[]
    for period in periods:
        x=complete_scopes(df[df.period==period],scopes)
        x['period']=period
        out.append(x)
    return pd.concat(out,ignore_index=True) if out else df

def reconciliation(actual,reported,tolerance=.05):
    if actual is None or reported is None or pd.isna(actual) or pd.isna(reported):return 'Not comparable'
    return 'Mismatch' if abs(actual-reported)>tolerance else 'Matches'

def product_store_reconciliation(products,shop,tolerance=.05):
    rows=[]
    if products.empty:return pd.DataFrame()
    for (country,marketplace,period,basis,currency),x in products.groupby(['country','marketplace','period','sales_basis','currency']):
        source=shop[(shop.country==country)&(shop.marketplace==marketplace)&(shop.period==period)&(shop.sales_basis==basis)&(shop.currency==currency)]
        product_total=total(x,'revenue');store_total=total(source,'gmv')
        rows.append({'Country':country,'Marketplace':marketplace,'Period':period,'Sales basis':basis,'Currency':currency,'Product total':product_total,'Store total':store_total,'Difference':pp(product_total,store_total),'Status':reconciliation(product_total,store_total,tolerance)})
    return pd.DataFrame(rows)
