from datetime import date
import pandas as pd
import pytest
from bosch_bi.engine import *


def test_reference_calculations_are_recomputed():
    assert growth(120,100)==pytest.approx(20)
    assert divide(120,150,100)==pytest.approx(80)
    assert reconciliation(growth(120,100),25)=='Mismatch'
    assert reconciliation(divide(120,150,100),75)=='Mismatch'

def test_undefined_vs_real_zero():
    assert divide(0,4)==0
    assert divide(4,0) is None
    assert growth(0,5)==-100
    assert growth(5,0) is None
    assert total(pd.DataFrame({'a':[2,None]}),'a') is None
    assert total(pd.DataFrame({'a':[0,0]}),'a')==0

def test_rates_are_weighted_not_averaged():
    df=pd.DataFrame({'rate':[10,90],'basis':[100,900]})
    assert weighted_rate(df,'rate','basis')==82
    assert weighted_rate(df.drop(columns='basis'),'rate','basis') is None
    assert weighted_rate(pd.DataFrame({'rate':[10,None],'basis':[1,1]}),'rate','basis') is None
    assert pp(1.44,2.32)==pytest.approx(-.88)
    assert favorable(pp(1.44,2.32),True)

def test_calendar_boundaries():
    assert previous_month('2026-01')=='2025-12'
    assert previous_year_period('2026-09')=='2025-09'
    assert comparable_dates('2024-02-01','2024-02-29')==(date(2023,2,1),date(2023,2,28))

def test_unique_audience_exact_interval_and_store():
    df=pd.DataFrame([dict(country='MY',marketplace='Shopee',period_start='2026-01-01',period_end='2026-01-31',visitors=100,buyers=10),dict(country='MY',marketplace='Shopee',period_start='2026-02-01',period_end='2026-02-28',visitors=100,buyers=10)])
    assert exact_audience(df,'2026-01-01','2026-02-28')==(None,None)
    assert exact_audience(df,'2026-01-01','2026-01-31')==(100,10)
    other=df.iloc[:1].copy();other['marketplace']='Lazada'
    assert exact_audience(pd.concat([df,other]),'2026-01-01','2026-01-31')==(None,None)

def test_fx_is_explicit_and_incomplete_fx_cannot_be_summed():
    df=pd.DataFrame({'period':['2026-01','2026-02'],'currency':['SGD','SGD'],'value':[10,20]})
    fx=pd.DataFrame([dict(period='2026-01',from_currency='SGD',to_currency='EUR',rate=.2,methodology='approved')])
    converted=convert(df,['value'],'EUR',fx,'approved')
    assert converted.value.iloc[0]==2
    assert pd.isna(converted.value.iloc[1])
    assert total(converted,'value') is None
    assert convert(df,['value'],'SGD',fx,'approved').value.tolist()==[10,20]

def test_scope_coverage_prevents_partial_consolidated_totals():
    df=pd.DataFrame([dict(country='MY',marketplace='Shopee',period='2026-01',tns=100)])
    complete=complete_months(df,[('MY','Shopee'),('MY','Lazada')],['2026-01','2026-02'])
    assert len(complete)==4
    assert total(complete,'tns') is None

def test_opportunity_evidence_gate():
    assert opportunity({'visitors':1000,'buyers':2,'cr':.2},500,1)=='Insufficient sample'
    assert opportunity({'visitors':1000,'buyers':10,'cr':1},500,2)=='Optimize listing'
    assert opportunity({'visitors':300,'buyers':20,'cr':6.6},500,2)=='Grow traffic'

def test_product_ranking_and_bundle_identity():
    master=pd.DataFrame([dict(country='MY',marketplace='Shopee',listing_sku=i,canonical_sku=i,product_name=i,business_unit='GT/PRO',product_group='Drills',is_bundle=i=='BUNDLE') for i in ['A','BUNDLE','NEW']])
    rows=[]
    for p,sku,revenue in [('2026-08','A',200),('2026-08','BUNDLE',100),('2026-09','A',100),('2026-09','BUNDLE',200),('2026-09','NEW',50)]:
        rows.append(dict(country='MY',marketplace='Shopee',listing_sku=sku,period=p,revenue=revenue,units=10,visitors=100,buyers=5))
    r=ranked_products(pd.DataFrame(rows),master,'2026-09','2026-08').set_index('canonical_sku')
    assert r.loc['BUNDLE','rank']==1
    assert r.loc['BUNDLE','rank_movement']==1
    assert r.loc['NEW','status']=='New entrant'
    assert bool(r.loc['BUNDLE','is_bundle'])
    assert r.loc['A','cr']==5

def test_product_unique_audience_not_added_across_platforms():
    master=pd.DataFrame([dict(country='MY',marketplace=p,listing_sku='A',canonical_sku='A',product_name='A',business_unit='GT/PRO',product_group='Drills',is_bundle=False) for p in ['Shopee','Lazada']])
    products=pd.DataFrame([dict(country='MY',marketplace=p,listing_sku='A',period='2026-09',revenue=100,units=5,visitors=100,buyers=2) for p in ['Shopee','Lazada']])
    r=ranked_products(products,master,'2026-09','2026-08')
    assert r.revenue.iloc[0]==200
    assert r.visitors.iloc[0] is None or pd.isna(r.visitors.iloc[0])
    assert r.cr.iloc[0] is None or pd.isna(r.cr.iloc[0])


def test_bosch_fixed_fx_policy_applies_in_both_directions_without_rate_files():
    import pandas as pd
    from bosch_bi.policy import EUR_TO_MYR
    source=pd.DataFrame({'period':['2026-01','2030-10'],'currency':['EUR','MYR'],'value':[1,4.64]})
    assert EUR_TO_MYR==4.64
    assert convert(source,['value'],'MYR',pd.DataFrame(),'anything').value.tolist()==[4.64,4.64]
    assert convert(source,['value'],'EUR',pd.DataFrame(),'anything').value.tolist()==[1,1]


def test_optional_forecast_audience_can_be_missing():
    target=pd.DataFrame([dict(country='MY',marketplace='Consolidated',period_start='2026-01-01',period_end='2026-12-31',visitors=None,buyers=None)])
    assert exact_audience(target,'2026-01-01','2026-12-31')==(None,None)
