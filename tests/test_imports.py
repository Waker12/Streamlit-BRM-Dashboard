import pandas as pd
import pytest
from bosch_bi.schemas import SCHEMAS,recognize,suggest_mapping
from bosch_bi.storage import Store,validate
from bosch_bi.demo import generate

@pytest.fixture
def store(tmp_path):return Store(tmp_path/'reporting.sqlite')

def sample(value=100,marketplace='Shopee',period='2026-09'):
    return pd.DataFrame([dict(country='MY',marketplace=marketplace,period=period,currency='MYR',tns=value)])

def test_all_demo_datasets_match_contracts():
    frames=generate()
    for key,df in frames.items():
        if df.empty:continue
        _,errors=validate(key,df,frames['sku_master'])
        assert not errors,(key,errors)

def test_duplicate_and_conflict_are_atomic(store):
    assert store.ingest('financial_actuals',sample(),'one.csv')['status']=='imported'
    assert store.ingest('financial_actuals',sample(),'renamed.csv')['status']=='duplicate'
    assert store.ingest('financial_actuals',sample(200),'changed.csv')['status']=='rejected'
    assert store.read('financial_actuals').tns.iloc[0]==100
    assert store.ingest('financial_actuals',sample(200),'changed.csv',True)['status']=='imported'
    assert store.read('financial_actuals').tns.iloc[0]==200
    assert len(store.history())==3

def test_history_and_cross_platform_keys_survive_restart(store):
    store.ingest('financial_actuals',sample(),'one.csv')
    store.ingest('financial_actuals',sample(marketplace='Lazada'),'two.csv')
    store.ingest('financial_actuals',sample(period='2026-08'),'three.csv')
    again=Store(store.path)
    assert len(again.read('financial_actuals'))==3
    assert len(again.history())==3

def test_invalid_batch_cannot_partially_commit(store):
    frame=pd.concat([sample(),sample(period='2026-08')],ignore_index=True)
    frame.loc[1,'tns']='unknown'
    assert store.ingest('financial_actuals',frame,'bad.csv')['status']=='rejected'
    assert store.read('financial_actuals').empty

def test_validation_rejects_grain_duplicate_bad_rates_and_audience():
    assert validate('financial_actuals',pd.concat([sample(),sample()]))[1]
    bad=sample();bad['gm_pct']=200
    assert validate('financial_actuals',bad)[1]
    traffic=pd.DataFrame([dict(country='MY',marketplace='Shopee',period_start='2026-09-01',period_end='2026-09-30',visitors=1,buyers=2)])
    assert validate('traffic',traffic)[1]
    bad=sample();bad['tns']=float('inf')
    assert validate('financial_actuals',bad)[1]

def test_product_master_required_and_bundle_conflicts(store):
    frames=generate();products=frames['products'].head(1)
    assert store.ingest('products',products,'product.csv')['status']=='rejected'
    master=frames['sku_master'].head(1)
    assert store.ingest('sku_master',master,'master.csv')['status']=='imported'
    assert store.ingest('products',products,'product.csv')['status']=='imported'
    conflicting=master.copy();conflicting['marketplace']='Lazada';conflicting['business_unit']='HD'
    assert store.ingest('sku_master',conflicting,'conflict.csv')['status']=='rejected'

def test_mapping_and_recognition():
    assert recognize(['tns','period'])=='financial_actuals'
    assert suggest_mapping(['Sales','Units Sold','SKU'],'products')=={'revenue':'Sales','units':'Units Sold','listing_sku':'SKU'}

def test_configs_persist(store):
    store.save_config('source',{'category':'financial_actuals','mapping':{'tns':'Net sales'}})
    assert Store(store.path).configs()['source']['mapping']['tns']=='Net sales'

def test_explicit_replacement_can_restore_earlier_report(store):
    assert store.ingest('financial_actuals',sample(100),'v1.csv')['status']=='imported'
    assert store.ingest('financial_actuals',sample(200),'v2.csv',True)['status']=='imported'
    assert store.ingest('financial_actuals',sample(100),'v1.csv',True)['status']=='imported'
    assert store.read('financial_actuals').tns.iloc[0]==100


def test_fixed_fx_override_cannot_be_imported():
    bad=pd.DataFrame([dict(period='2026-01',from_currency='EUR',to_currency='MYR',rate=5,methodology='other')])
    assert validate('fx',bad)[1]

def test_atomic_source_bundle_rolls_back_all_datasets(store):
    good=sample()
    bad=pd.DataFrame([dict(country='MY',marketplace='Shopee',period='2026-09',currency='MYR',sales_basis='Placed Order',gmv='invalid')])
    assert store.ingest_bundle({'financial_actuals':good,'marketplace':bad},'bad-source.xlsx')['status']=='rejected'
    assert store.read('financial_actuals').empty
    assert store.read('marketplace').empty
    assert len(store.history())==1
