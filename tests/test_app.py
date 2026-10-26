from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/'app.py'
PAGES=['Executive overview','Financial performance','Marketplace performance','Product & SKU','Conversion analysis','Advertising performance','BRM workbook','Data workspace','Reporting methodology']

@pytest.fixture
def app(tmp_path,monkeypatch):
    monkeypatch.setenv('BOSCH_BI_DB',str(tmp_path/'app.sqlite'))
    return AppTest.from_file(str(APP),default_timeout=45).run()

def test_all_pages_demo_and_empty_uploaded(app):
    assert not app.exception
    for page in PAGES:
        app.radio[0].set_value(page).run()
        assert not app.exception,(page,[x.message for x in app.exception])
    app.radio[1].set_value('Uploaded data').run()
    for page in PAGES:
        app.radio[0].set_value(page).run()
        assert not app.exception,(page,[x.message for x in app.exception])

def test_consolidated_and_alternate_currency(app):
    assert app.selectbox(key='country').options==['Malaysia']
    app.selectbox(key='marketplace').set_value('All marketplaces').run()
    app.selectbox(key='currency').set_value('SGD').run()
    assert not app.exception
    for page in ['Marketplace performance','Product & SKU','Conversion analysis','Advertising performance']:
        app.radio[0].set_value(page).run()
        assert not app.exception,(page,[x.message for x in app.exception])

def test_monthly_january_and_missing_year(app):
    app.selectbox(key='month').set_value(1).run()
    app.selectbox(key='period_mode').set_value('Selected month').run()
    for page in ['Financial performance','Marketplace performance','Product & SKU']:
        app.radio[0].set_value(page).run()
        assert not app.exception
    app.selectbox(key='year').set_value(2024).run()
    app.radio[0].set_value('Executive overview').run()
    assert not app.exception

def test_uploaded_canonical_data_renders_all_modules(tmp_path,monkeypatch):
    from bosch_bi.storage import Store
    from bosch_bi.demo import generate
    path=tmp_path/'uploaded.sqlite'
    monkeypatch.setenv('BOSCH_BI_DB',str(path))
    store=Store(path);frames=generate()
    for key in ['sku_master','fx','financial_actuals','forecasts','marketplace','traffic','products','ads']:
        assert store.ingest(key,frames[key],f'{key}.csv')['status']=='imported'
    app=AppTest.from_file(str(APP),default_timeout=45).run()
    app.radio[1].set_value('Uploaded data').run()
    for page in PAGES:
        app.radio[0].set_value(page).run()
        assert not app.exception,(page,[x.message for x in app.exception])


def test_supplied_sources_render_finance_marketplace_and_excerpt_views(tmp_path,monkeypatch):
    import os,json
    if not os.environ.get('BOSCH_SOURCE_MANIFEST'):pytest.skip('Private source files are not bundled')
    from bosch_bi.storage import Store
    from bosch_bi.adapters import parse_source
    path=tmp_path/'real.sqlite';monkeypatch.setenv('BOSCH_BI_DB',str(path))
    store=Store(path)
    for f in json.loads(Path(os.environ['BOSCH_SOURCE_MANIFEST']).read_text()):
        source=parse_source(Path(f['path']).read_bytes())
        assert store.ingest_bundle(source.datasets,Path(f['path']).name)['status']=='imported'
    app=AppTest.from_file(str(APP),default_timeout=45).run()
    assert app.radio[1].value=='Uploaded data'
    assert not app.exception
    expected=store.read('financial_actuals').query("period >= '2026-01' and period <= '2026-09'").tns.sum()
    assert app.metric[0].value==f'EUR {expected:,.0f}'
    assert all(m.delta!='—' for m in app.metric)
    for page in PAGES:
        app.radio[0].set_value(page).run()
        assert not app.exception,(page,[x.message for x in app.exception])
    app.radio[0].set_value('Financial performance').run()
    app.selectbox(key='currency').set_value('MYR').run()
    assert not app.exception
    assert app.metric[0].value==f'MYR {expected*4.64:,.0f}'
    app.radio[0].set_value('Marketplace performance').run()
    app.selectbox(key='marketplace').set_value('Shopee').run()
    app.selectbox(key='order_basis').set_value('Confirmed Order').run()
    assert not app.exception

def test_supplied_product_views_and_missing_fx(tmp_path,monkeypatch):
    import os,json
    if not os.environ.get('BOSCH_PRODUCT_MANIFEST'):pytest.skip('Private product files are not bundled')
    from bosch_bi.storage import Store
    from bosch_bi.adapters import parse_source,period_from_filename
    path=tmp_path/'products.sqlite';monkeypatch.setenv('BOSCH_BI_DB',str(path))
    store=Store(path)
    for f in json.loads(Path(os.environ['BOSCH_PRODUCT_MANIFEST']).read_text()):
        raw=Path(f['path']);source=parse_source(raw.read_bytes(),period=period_from_filename(raw.name))
        assert store.ingest_bundle(source.datasets,raw.name)['status']=='imported'
    app=AppTest.from_file(str(APP),default_timeout=60).run()
    app.radio[1].set_value('Uploaded data').run()
    for page in ['Product & SKU','Conversion analysis']:
        app.radio[0].set_value(page).run()
        assert not app.exception,(page,[x.message for x in app.exception])
        app.selectbox(key='currency').set_value('SGD').run()
        assert not app.exception,(page,[x.message for x in app.exception])
        app.selectbox(key='currency').set_value('EUR').run()
    app.radio[0].set_value('Product & SKU').run()
    next(x for x in app.selectbox if x.label=='Product reporting grain').set_value('Sellable variant detail').run()
    assert not app.exception
